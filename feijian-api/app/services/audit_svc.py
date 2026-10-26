"""审计日志：写失败不阻断主业务（审计与业务解耦，失败仅记服务端日志）。"""

import logging

from sqlalchemy.orm import Session

from app.models import AuditLog

_logger = logging.getLogger("app.audit")


def log(
    db: Session,
    user_id: int | None,
    action: str,
    target: str | None = None,
    detail: dict | None = None,
    ip: str | None = None,
):
    try:
        db.add(AuditLog(user_id=user_id, action=action, target=target, detail=detail or {}, ip=ip))
        db.commit()
    except Exception:
        db.rollback()
        _logger.exception("audit log failed: action=%s target=%s", action, target)
