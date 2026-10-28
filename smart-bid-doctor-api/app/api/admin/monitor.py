"""监控与告警端点（05 §4 / §10）：大盘聚合 / 任务巡检 / 告警列表与确认。

权限点：admin:monitor:read | admin:monitor:alert。告警确认写审计（alert_ack）。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_perm
from app.models import User
from app.schemas.platform import AlertPage, MonitorOverviewOut, OkOut, TaskAdminPage
from app.services import alert_svc, audit_svc, monitor_svc

router = APIRouter(tags=["admin-monitor"])

A = audit_svc.AuditAction


@router.get("/monitor/overview", response_model=MonitorOverviewOut)
def overview(_: User = Depends(require_perm("admin:monitor:read")), db: Session = Depends(get_db)):
    data = monitor_svc.overview(db)
    return MonitorOverviewOut(
        tasks=data["tasks"], llm=data["llm"], capacity=data["capacity"],
        unacked_alerts=alert_svc.unacked_count(db),
    )


@router.get("/monitor/tasks", response_model=TaskAdminPage)
def monitor_tasks(
    status: str | None = None,
    type: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:monitor:read")),
    db: Session = Depends(get_db),
):
    rows, total = monitor_svc.task_list(db, status=status, type_=type, limit=limit, offset=offset)
    return TaskAdminPage(items=rows, total=total)


@router.get("/monitor/storage", response_model=dict)
def storage(_: User = Depends(require_perm("admin:monitor:read")), db: Session = Depends(get_db)):
    return monitor_svc.disk_usage(db)


@router.get("/alerts", response_model=AlertPage)
def list_alerts(
    acked: bool | None = None,
    level: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:monitor:alert")),
    db: Session = Depends(get_db),
):
    rows, total, unacked = alert_svc.list_alerts(
        db, acked=acked, level=level, limit=limit, offset=offset,
    )
    return AlertPage(items=rows, total=total, unacked=unacked)


@router.post("/alerts/{alert_id}/ack", response_model=OkOut)
def ack_alert(
    alert_id: int,
    admin: User = Depends(require_perm("admin:monitor:alert")),
    db: Session = Depends(get_db),
):
    alert_svc.ack(db, alert_id, admin.id)
    audit_svc.log(db, admin.id, A.ALERT_ACK, target=f"alert:{alert_id}")
    return OkOut()
