"""运营指标聚合（04 §6）——internal metrics API 与 scripts/daily_report.py 共用，单一实现。"""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import LlmCall, Task


def daily_stats(db: Session, day_start: dt.datetime, day_end: dt.datetime) -> dict:
    """昨日/当日运营指标：任务分布、平均耗时、LLM 成本、失败 top 错误码、当前积压。"""
    rows = (
        db.query(Task.status, sa.func.count(Task.id))
        .filter(Task.created_at >= day_start, Task.created_at < day_end)
        .group_by(Task.status)
        .all()
    )
    by_status = {status: int(n) for status, n in rows}
    total = sum(by_status.values())
    succeeded = by_status.get("succeeded", 0)
    avg_secs = (
        db.query(
            sa.func.avg(
                sa.extract("epoch", Task.finished_at) - sa.extract("epoch", Task.created_at)
            )
        )
        .filter(
            Task.created_at >= day_start,
            Task.created_at < day_end,
            Task.finished_at.is_not(None),
        )
        .scalar()
    )
    top_errors = (
        db.query(Task.error_code, sa.func.count(Task.id))
        .filter(
            Task.created_at >= day_start,
            Task.created_at < day_end,
            Task.status == "failed",
            Task.error_code.is_not(None),
        )
        .group_by(Task.error_code)
        .order_by(sa.func.count(Task.id).desc())
        .limit(5)
        .all()
    )
    cost = (
        db.query(sa.func.coalesce(sa.func.sum(LlmCall.cost_cny), 0))
        .filter(LlmCall.created_at >= day_start, LlmCall.created_at < day_end)
        .scalar()
    )
    backlog = (
        db.query(sa.func.count(Task.id)).filter(Task.status == "pending").scalar() or 0
    )
    return {
        "tasks_total": total,
        "tasks_by_status": by_status,
        "success_rate": round(succeeded / total, 4) if total else None,
        "avg_duration_secs": round(float(avg_secs), 1) if avg_secs is not None else None,
        "llm_cost_cny": float(cost),
        "top_error_codes": [{"code": code, "count": int(n)} for code, n in top_errors],
        "pending_backlog": int(backlog),
    }
