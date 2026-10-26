"""任务执行器：claim（SKIP LOCKED）→ dispatch → 状态机（02 §8）。
骨架版 handler 全部为桩（详见 handlers/），只验证队列与状态流转，不含业务逻辑。"""

import datetime as dt
import logging
import time

import sqlalchemy as sa

from app.core.db import SessionLocal
from app.models import Task
from app.worker.handlers import checklist, compare, embed, extract, parse

log = logging.getLogger("worker")

HANDLERS = {
    "parse": parse.run,
    "extract": extract.run,
    "embed": embed.run,
    "checklist": checklist.run,
    "compare": compare.run,
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


def recover_stale() -> None:
    """心跳超时的 running 任务：attempt 未满回 pending（退避 30s），否则 failed（02 §8）"""
    with SessionLocal() as db:
        stale = (
            db.query(Task)
            .filter(
                Task.status == "running",
                Task.heartbeat_at < dt.datetime.now(dt.UTC) - STALE_HEARTBEAT,
            )
            .all()
        )
        for t in stale:
            if t.attempt < MAX_ATTEMPT:
                t.status = "pending"
                t.run_after = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=30)
            else:
                t.status = "failed"
                t.error_code = "WORKER_TIMEOUT"
                t.finished_at = dt.datetime.now(dt.UTC)
        db.commit()


def _fail(task_id: int, code: str, msg: str) -> None:
    with SessionLocal() as db:
        t = db.get(Task, task_id)
        if t is None:
            return
        t.status = "failed"
        t.error_code = code
        t.error_msg = msg
        t.finished_at = dt.datetime.now(dt.UTC)
        db.commit()


def main_loop(poll: float = 3.0) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    log.info("worker started, handlers=%s", list(HANDLERS))
    while True:
        row = None
        try:
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
                _fail(dict(row)["id"], "HANDLER_CRASH", "handler 异常，详见服务端日志")


if __name__ == "__main__":
    main_loop()
