"""定时任务管理（sys_job / sys_job_log，05 §3.4）。

调度元数据入 sys_job；执行触发两条路：
- queue 型（handler="purge"）：INSERT tasks 复用任务队列状态机；
- inline 型（stats_rollup / alert_scan / reconcile / daily_report）：worker 进程内
  直接执行，结果写 sys_job_log——都不破坏 tasks 状态机（02 §8）。
cron 表达式 5 字段标准格式，next_run_at 由 croniter 计算。
"""

import datetime as dt
import logging

from croniter import croniter
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import SysJob, SysJobLog

_logger = logging.getLogger("app.job")

# worker 内联执行器注册表（job_key → 可调用，签名 (db) -> dict 摘要）；
# runner 主循环按 sys_job.next_run_at 到期调度。purge 特殊：入 tasks 队列。
INLINE_JOBS: dict[str, object] = {}
QUEUE_JOBS = {"purge"}  # 复用 tasks 队列的 job


def register_inline(job_key: str):
    def deco(fn):
        INLINE_JOBS[job_key] = fn
        return fn
    return deco


def next_run(cron_expr: str, after: dt.datetime) -> dt.datetime:
    try:
        return croniter(cron_expr, after).get_next(dt.datetime)
    except (ValueError, KeyError) as exc:
        raise AppError(400, "CONFIG_VALUE_INVALID", "cron 表达式不合法") from exc


def validate_cron(cron_expr: str) -> bool:
    try:
        croniter(cron_expr)
        return True
    except (ValueError, KeyError):
        return False


def list_jobs(db: Session) -> list[SysJob]:
    return db.query(SysJob).order_by(SysJob.id.asc()).all()


def list_logs(db: Session, job_key: str, *, limit: int = 20, offset: int = 0) -> tuple[list[SysJobLog], int]:
    q = db.query(SysJobLog).filter(SysJobLog.job_key == job_key)
    total = q.count()
    return q.order_by(SysJobLog.id.desc()).offset(offset).limit(min(limit, 100)).all(), total


def set_enabled(db: Session, job_id: int, enabled: bool) -> SysJob:
    row = _get(db, job_id)
    row.enabled = enabled
    if enabled:
        row.next_run_at = next_run(row.cron_expr, dt.datetime.now(dt.UTC))
    row.updated_at = dt.datetime.now(dt.UTC)
    db.commit()
    return row


def trigger(db: Session, job_id: int) -> SysJob:
    """手动触发：把 next_run_at 拉到现在，由 worker 主循环在数秒内领取执行。"""
    row = _get(db, job_id)
    row.next_run_at = dt.datetime.now(dt.UTC)
    row.updated_at = dt.datetime.now(dt.UTC)
    db.commit()
    return row


def due_jobs(db: Session, now: dt.datetime) -> list[SysJob]:
    """到期任务快照（enabled 且 next_run_at<=now）。调度器负责认领与推进。"""
    return (
        db.query(SysJob)
        .filter(SysJob.enabled.is_(True), SysJob.next_run_at.is_not(None),
                SysJob.next_run_at <= now)
        .all()
    )


def claim(db: Session, job_id: int, cron_expr: str) -> bool:
    """原子认领：单条 UPDATE 把 next_run_at 推进到下一周期 + 刷 last_run_at。

    多 worker 并发时仅一个 rowcount=1 认领成功（乐观锁语义，幂等安全）。
    """
    now = dt.datetime.now(dt.UTC)
    res = db.execute(
        sa_update_job(job_id, next_run_at=next_run(cron_expr, now), last_run_at=now)
    )
    db.commit()
    return res.rowcount > 0


def sa_update_job(job_id: int, **values):
    import sqlalchemy as sa
    return sa.update(SysJob).where(SysJob.id == job_id).values(**values)


def write_log(db: Session, *, job_key: str, job_id: int | None, status: str,
              cost_ms: int | None, result: dict | None, error: str | None) -> None:
    """运行结果落 sys_job_log（独立 commit；连续失败告警由 alert_scan 巡检扫描）。"""
    db.add(SysJobLog(
        job_id=job_id, job_key=job_key, status=status,
        cost_ms=cost_ms, result=result, error=error,
    ))
    db.commit()


def run_inline(db: Session, job: SysJob) -> dict:
    """执行 inline job 并写运行日志；未注册 handler 记 fail（不抛出）。"""
    started = dt.datetime.now(dt.UTC)
    try:
        fn = INLINE_JOBS.get(job.job_key)
        if fn is None:
            # 未注册执行器按失败落日志（不外抛）：HANDLER_CRASH 是 worker 专用码，
            # 禁止经 AppError 冒用（见 errors.py 注册表与 test_errors_registry 守卫）
            raise RuntimeError(f"job {job.job_key} 未注册执行器")
        result = fn(db)
        cost = int((dt.datetime.now(dt.UTC) - started).total_seconds() * 1000)
        write_log(db, job_key=job.job_key, job_id=job.id, status="ok",
                  cost_ms=cost, result=result, error=None)
        return result or {}
    except Exception as exc:
        cost = int((dt.datetime.now(dt.UTC) - started).total_seconds() * 1000)
        _logger.exception("inline job failed: %s", job.job_key)
        write_log(db, job_key=job.job_key, job_id=job.id, status="fail",
                  cost_ms=cost, result=None, error=str(exc)[:2000])
        return {"error": str(exc)}


def _get(db: Session, job_id: int) -> SysJob:
    row = db.get(SysJob, job_id)
    if row is None:
        raise AppError(404, "JOB_NOT_FOUND", "定时任务不存在")
    return row
