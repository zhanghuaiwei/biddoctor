"""审计日志：写失败不阻断主业务（审计与业务解耦，失败仅记服务端日志）。

留痕规范（skill: biddoctor-engineering）：所有审计 detail 自动关联 request_id，
使 audit_logs ↔ 结构化日志 ↔ tasks.task_id 可互查，形成功能全生命周期留痕链。
"""

import ipaddress
import logging

from sqlalchemy.orm import Session

from app.core.logging import request_id_var
from app.models import AuditLog

_logger = logging.getLogger("app.audit")


def _safe_ip(ip: str | None) -> str | None:
    """INET 列只接受合法 IP；非法值（unix socket/testclient 等）归 NULL。"""
    if not ip:
        return None
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None


def log(
    db: Session,
    user_id: int | None,
    action: str,
    target: str | None = None,
    detail: dict | None = None,
    ip: str | None = None,
):
    # detail 自动附带 request_id（无请求上下文时为 "-"）
    payload = {"request_id": request_id_var.get(), **(detail or {})}
    try:
        db.add(
            AuditLog(
                user_id=user_id, action=action, target=target,
                detail=payload, ip=_safe_ip(ip),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        _logger.exception("audit log failed: action=%s target=%s", action, target)
