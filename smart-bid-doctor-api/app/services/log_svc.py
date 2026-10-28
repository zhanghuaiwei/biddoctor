"""审计与日志三表（05 §5）：audit_logs（业务动作）/ sys_login_log（登录全量）/
sys_oper_log（管理端请求级）。查询分页 + CSV 导出（导出动作本身写 log_export 审计）。

写入口：
- login_log：auth_svc 登录尝试成功/失败各落一行（独立事务，不阻断主流程）；
- oper_log：main.py 管理端中间件逐请求落行（仅 /api/admin/*，query 摘要脱敏，
  不记请求体——避免凭据类字段入日志）。
"""

import csv
import datetime as dt
import io
import logging

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import AuditLog, SysLoginLog, SysOperLog, User
from app.services.audit_svc import _safe_ip

_logger = logging.getLogger("app.operlog")

# 登录日志 180 天 / 操作日志 180 天留存（purge 任务按此清理，05 §5.1 表 3）
RETENTION_DAYS = 180

_MAX_UA = 256
_MAX_QUERY = 512


def write_login_log(db: Session, *, user_id: int | None, email: str | None,
                    result: str, fail_reason: str | None, ip: str,
                    user_agent: str | None) -> None:
    """每次登录尝试落一行；独立 commit，失败仅记日志不阻断登录主流程。"""
    try:
        db.add(SysLoginLog(
            user_id=user_id, email=(email or "")[:320] or None, result=result,
            fail_reason=fail_reason, ip=_safe_ip(ip),
            user_agent=(user_agent or "")[:_MAX_UA] or None,
        ))
        db.commit()
    except Exception:
        db.rollback()
        _logger.exception("login log failed")


def write_oper_log(db: Session, *, user_id: int | None, module: str, action: str,
                   method: str, path: str, status_code: int, cost_ms: int,
                   query: str | None, ip: str) -> None:
    try:
        db.add(SysOperLog(
            user_id=user_id, module=module, action=action, method=method,
            path=path[:128], status_code=status_code, cost_ms=cost_ms,
            request={"query": (query or "")[:_MAX_QUERY]} if query else None,
            ip=_safe_ip(ip),
        ))
        db.commit()
    except Exception:
        db.rollback()
        _logger.exception("oper log failed")


# ── 分页查询（管理端三张日志统一形态）───────────────────────────────────────


def list_login_logs(db: Session, *, email: str | None = None, result: str | None = None,
                    limit: int = 20, offset: int = 0) -> tuple[list[SysLoginLog], int]:
    q = db.query(SysLoginLog)
    if email:
        q = q.filter(SysLoginLog.email.ilike(f"%{email.lower()}%"))
    if result:
        q = q.filter(SysLoginLog.result == result)
    total = q.count()
    return q.order_by(SysLoginLog.id.desc()).offset(offset).limit(min(limit, 100)).all(), total


def list_oper_logs(db: Session, *, module: str | None = None,
                   limit: int = 20, offset: int = 0) -> tuple[list[SysOperLog], int]:
    q = db.query(SysOperLog)
    if module:
        q = q.filter(SysOperLog.module == module)
    total = q.count()
    return q.order_by(SysOperLog.id.desc()).offset(offset).limit(min(limit, 100)).all(), total


def list_audit_logs(db: Session, *, action: str | None = None, user_id: int | None = None,
                    limit: int = 20, offset: int = 0) -> tuple[list[AuditLog], int]:
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if user_id is not None:
        q = q.filter(AuditLog.user_id == user_id)
    total = q.count()
    return q.order_by(AuditLog.id.desc()).offset(offset).limit(min(limit, 100)).all(), total


def list_actions(db: Session) -> list[str]:
    """审计 action 去重清单（管理端筛选下拉）。"""
    rows = db.execute(sa.select(AuditLog.action).distinct().order_by(AuditLog.action)).all()
    return [r[0] for r in rows]


def user_email_map(db: Session, user_ids: list[int | None]) -> dict[int, str]:
    ids = {i for i in user_ids if i}
    if not ids:
        return {}
    rows = db.query(User.id, User.email).filter(User.id.in_(ids)).all()
    return {r[0]: r[1] for r in rows}


# ── CSV 导出 ─────────────────────────────────────────────────────────────────


def rows_to_csv(headers: list[str], rows: list[list]) -> bytes:
    """UTF-8 BOM 头（Excel 直接打开不乱码）。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def export_login_logs(db: Session, *, max_rows: int = 10000) -> bytes:
    rows = (
        db.query(SysLoginLog).order_by(SysLoginLog.id.desc()).limit(max_rows).all()
    )
    return rows_to_csv(
        ["id", "user_id", "email", "result", "fail_reason", "ip", "user_agent", "created_at"],
        [[r.id, r.user_id, r.email, r.result, r.fail_reason, r.ip, r.user_agent,
          r.created_at.isoformat()] for r in rows],
    )


def export_oper_logs(db: Session, *, max_rows: int = 10000) -> bytes:
    rows = (
        db.query(SysOperLog).order_by(SysOperLog.id.desc()).limit(max_rows).all()
    )
    return rows_to_csv(
        ["id", "user_id", "module", "action", "method", "path", "status_code",
         "cost_ms", "ip", "created_at"],
        [[r.id, r.user_id, r.module, r.action, r.method, r.path, r.status_code,
          r.cost_ms, r.ip, r.created_at.isoformat()] for r in rows],
    )


def export_audit_logs(db: Session, *, max_rows: int = 10000) -> bytes:
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(max_rows).all()
    return rows_to_csv(
        ["id", "user_id", "action", "target", "detail", "ip", "created_at"],
        [[r.id, r.user_id, r.action, r.target,
          str(r.detail)[:500], r.ip, r.created_at.isoformat()] for r in rows],
    )


def purge_expired(db: Session, now: dt.datetime) -> int:
    """物理清理超留存期的登录/操作日志（worker purge 生命周期任务调用，唯一硬删入口之一）。"""
    cutoff = now - dt.timedelta(days=RETENTION_DAYS)
    n1 = db.query(SysLoginLog).filter(SysLoginLog.created_at < cutoff).delete()
    n2 = db.query(SysOperLog).filter(SysOperLog.created_at < cutoff).delete()
    return int(n1) + int(n2)
