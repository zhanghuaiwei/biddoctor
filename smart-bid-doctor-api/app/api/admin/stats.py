"""统计报表端点（05 §6 / §10）：T+1 汇总查询 + CSV 导出。权限点 admin:stats:read。"""

import datetime as dt
from datetime import date as date_t

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_perm
from app.models import User
from app.schemas.platform import StatRowOut
from app.services import audit_svc, stats_svc

router = APIRouter(tags=["admin-stats"])

A = audit_svc.AuditAction


@router.get("/stats/daily", response_model=list[StatRowOut])
def stats_daily(
    dim: str | None = None,
    metric: str | None = None,
    from_: date_t | None = Query(default=None, alias="from"),
    to: date_t | None = None,
    _: User = Depends(require_perm("admin:stats:read")),
    db: Session = Depends(get_db),
):
    return stats_svc.query_daily(db, dim=dim, metric=metric, from_=from_, to=to)


@router.get("/stats/daily/export")
def export_stats(
    dim: str | None = None,
    metric: str | None = None,
    from_: date_t | None = Query(default=None, alias="from"),
    to: date_t | None = None,
    admin: User = Depends(require_perm("admin:stats:read")),
    db: Session = Depends(get_db),
):
    content = stats_svc.export_daily(db, dim=dim, metric=metric, from_=from_, to=to)
    audit_svc.log(db, admin.id, A.LOG_EXPORT, target="stats/daily")
    return Response(
        content=content, media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="stats-{dt.date.today().isoformat()}.csv"',
        },
    )


@router.post("/stats/rollup", response_model=dict)
def manual_rollup(
    day: date_t | None = None,
    admin: User = Depends(require_perm("admin:stats:read")),
    db: Session = Depends(get_db),
):
    """手动补算（T+1 定时之外的运维兜底）。"""
    target = day or (dt.date.today() - dt.timedelta(days=1))
    return stats_svc.rollup_day(db, target)
