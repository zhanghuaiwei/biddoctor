"""任务执行器：claim（SKIP LOCKED）→ dispatch → 状态机（02 §8）。
骨架版 handler 全部为桩（详见 handlers/），只验证队列与状态流转，不含业务逻辑。
内置 cron 型任务：每日一条 type='purge'（03 §5 数据生命周期）。"""

import datetime as dt
import logging
import time

import sqlalchemy as sa

from app.core.db import SessionLocal
from app.core.enums import TaskStatus, TaskType
from app.models import Task
from app.worker import heartbeat
from app.worker.handlers import checklist, compare, embed, extract, parse, purge

log = logging.getLogger("worker")

HANDLERS = {
    "parse": parse.run,
    "extract": extract.run,
    "embed": embed.run,
    "checklist": checklist.run,
    "compare": compare.run,
    "purge": purge.run,
}

CLAIM_SQL = sa.text(
    """
    UPDATE tasks SET status='running', heartbeat_at=now(), attempt=attempt+1
    WHERE id = (
        SELECT id FROM tasks
        WHERE status='pending' AND run_after <= now()
        ORDER BY created_at
        FOR UPDATE SKIP LOCKED LIMIT 1
    )
    RETURNING id, type, project_id, document_id, comparison_id, attempt
    """
)

STALE_HEARTBEAT = dt.timedelta(seconds=300)
MAX_ATTEMPT = 3

# purge 调度（03 §5：每日 03:00）。部署基线为香港服务器（UTC+8），按北京时间触发；
# 固定偏移无夏令时问题。任务幂等：每个北京日只建一条。
PURGE_TZ_OFFSET = dt.timedelta(hours=8)
PURGE_AT = dt.time(3, 5)


def enqueue_daily_purge(bj_now: dt.datetime | None = None) -> int | None:
    """北京时间每日 03:05 后创建当日 purge 任务（幂等），返回任务 id 或 None。
    bj_now 可注入便于测试。"""
    if bj_now is None:
        bj_now = dt.datetime.now(dt.UTC) + PURGE_TZ_OFFSET
    if bj_now.tzinfo is None:
        bj_now = bj_now.replace(tzinfo=dt.UTC)
    if bj_now.time() < PURGE_AT:
        return None
    day_start_utc = (
        dt.datetime.combine(bj_now.date(), dt.time.min) - PURGE_TZ_OFFSET
    ).replace(tzinfo=dt.UTC)
    with SessionLocal() as db:
        exists = (
            db.query(Task.id)
            .filter(Task.type == TaskType.PURGE, Task.created_at >= day_start_utc)
            .first()
        )
        if exists:
            return None
        t = Task(type=TaskType.PURGE, status=TaskStatus.PENDING, run_after=dt.datetime.now(dt.UTC))
        db.add(t)
        db.commit()
        log.info("daily purge task created id=%s (bj date %s)", t.id, bj_now.date())
        return t.id


def recover_stale() -> None:
    """心跳超时的 running 任务：attempt 未满回 pending（退避 30s），否则 failed（02 §8）"""
    with SessionLocal() as db:
        stale = (
            db.query(Task)
            .filter(
                Task.status == TaskStatus.RUNNING,
                Task.heartbeat_at < dt.datetime.now(dt.UTC) - STALE_HEARTBEAT,
            )
            .all()
        )
        for t in stale:
            if t.attempt < MAX_ATTEMPT:
                t.status = TaskStatus.PENDING
                t.run_after = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=30)
            else:
                t.status = TaskStatus.FAILED
                t.error_code = "WORKER_TIMEOUT"
                t.finished_at = dt.datetime.now(dt.UTC)
        db.commit()


def _fail(task_id: int, code: str, msg: str) -> None:
    with SessionLocal() as db:
        t = db.get(Task, task_id)
        if t is None:
            return
        t.status = TaskStatus.FAILED
        t.error_code = code
        t.error_msg = msg
        t.finished_at = dt.datetime.now(dt.UTC)
        db.commit()


def _requeue(task_id: int, delay_secs: int = 30) -> None:
    """可恢复错误回 pending（02 §8 状态机：进程重启/超时类重试）"""
    with SessionLocal() as db:
        t = db.get(Task, task_id)
        if t is None:
            return
        t.status = TaskStatus.PENDING
        t.run_after = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=delay_secs)
        db.commit()


def main_loop(poll: float = 3.0) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    log.info("worker started, handlers=%s", list(HANDLERS))
    heartbeat.start_heartbeat_thread()
    while True:
        row = None
        try:
            enqueue_daily_purge()
            recover_stale()
            with SessionLocal() as db:
                row = db.execute(CLAIM_SQL).mappings().first()
            if row is None:
                time.sleep(poll)
                continue
            task = dict(row)
            log.info("claimed task %s type=%s attempt=%s", task["id"], task["type"], task["attempt"])
            handler = HANDLERS.get(task["type"])
            if handler is None:
                _fail(task["id"], "UNKNOWN_TASK_TYPE", f"未知任务类型 {task['type']}")
                continue
            with SessionLocal() as db:
                handler(task, db)
        except Exception:
            log.exception("task execution error")
            if row is not None:
                r = dict(row)
                # 02 §8：异常不区分类型时按可恢复处理——attempt 未满回 pending 退避重试，
                # 满了才 failed（确定性失败应由 handler 内部显式 _fail，不走这里）
                if r["attempt"] < MAX_ATTEMPT:
                    _requeue(r["id"], delay_secs=30 * r["attempt"])
                else:
                    _fail(r["id"], "HANDLER_CRASH", "handler 异常，详见服务端日志")


if __name__ == "__main__":
    main_loop()
