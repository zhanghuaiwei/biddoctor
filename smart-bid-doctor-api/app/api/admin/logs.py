"""日志查询端点（05 §5 / §10）：审计 / 登录 / 操作三表分页 + CSV 导出。

权限点：admin:log:read。导出动作本身写审计（log_export，05 §5.2）。
"""

import datetime as dt

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_perm
from app.models import User
from app.schemas.platform import AuditLogOut, AuditLogPage, LoginLogPage, OperLogPage
from app.services import audit_svc, log_svc

router = APIRouter(tags=["admin-logs"])

A = audit_svc.AuditAction

_CSV_MEDIA = "text/csv; charset=utf-8"


def _export_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content, media_type=_CSV_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/logs/audit", response_model=AuditLogPage)
def audit_logs(
    action: str | None = None,
    user_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:log:read")),
    db: Session = Depends(get_db),
):
    rows, total = log_svc.list_audit_logs(db, action=action, user_id=user_id,
                                          limit=limit, offset=offset)
    emails = log_svc.user_email_map(db, [r.user_id for r in rows])
    items = [
        AuditLogOut.model_validate(r).model_copy(update={"user_email": emails.get(r.user_id)})
        for r in rows
    ]
    return AuditLogPage(items=items, total=total)


@router.get("/logs/audit/export")
def export_audit_logs(
    admin: User = Depends(require_perm("admin:log:read")),
    db: Session = Depends(get_db),
):
    content = log_svc.export_audit_logs(db)
    audit_svc.log(db, admin.id, A.LOG_EXPORT, target="logs/audit")
    return _export_response(content, f"audit-logs-{dt.date.today().isoformat()}.csv")


@router.get("/logs/audit/actions", response_model=list[str])
def audit_actions(_: User = Depends(require_perm("admin:log:read")), db: Session = Depends(get_db)):
    return log_svc.list_actions(db)


@router.get("/logs/login", response_model=LoginLogPage)
def login_logs(
    email: str | None = None,
    result: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:log:read")),
    db: Session = Depends(get_db),
):
    rows, total = log_svc.list_login_logs(db, email=email, result=result,
                                          limit=limit, offset=offset)
    return LoginLogPage(items=rows, total=total)


@router.get("/logs/login/export")
def export_login_logs(
    admin: User = Depends(require_perm("admin:log:read")),
    db: Session = Depends(get_db),
):
    content = log_svc.export_login_logs(db)
    audit_svc.log(db, admin.id, A.LOG_EXPORT, target="logs/login")
    return _export_response(content, f"login-logs-{dt.date.today().isoformat()}.csv")


@router.get("/logs/oper", response_model=OperLogPage)
def oper_logs(
    module: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:log:read")),
    db: Session = Depends(get_db),
):
    rows, total = log_svc.list_oper_logs(db, module=module, limit=limit, offset=offset)
    return OperLogPage(items=rows, total=total)


@router.get("/logs/oper/export")
def export_oper_logs(
    admin: User = Depends(require_perm("admin:log:read")),
    db: Session = Depends(get_db),
):
    content = log_svc.export_oper_logs(db)
    audit_svc.log(db, admin.id, A.LOG_EXPORT, target="logs/oper")
    return _export_response(content, f"oper-logs-{dt.date.today().isoformat()}.csv")
