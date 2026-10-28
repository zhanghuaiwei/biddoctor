"""告警（sys_alert_log，05 §4）：阈值入 sys_config（alert.* 键），触发落表 + ack 闭环。

去抖：同 rule_key 存在未确认告警时不重复触发（避免每分钟巡检刷屏）；
通知渠道 MVP 阶段写服务端日志 + 管理端红点，webhook 预留（D8 邮箱通道复用）。
"""

import datetime as dt
import logging

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.enums import NoticeLevel
from app.core.errors import AppError
from app.models import SysAlertLog

_logger = logging.getLogger("app.alert")


def trigger_if_needed(db: Session, *, rule_key: str, level: str, title: str,
                      content: str, metric: dict) -> bool:
    """触发告警（同规则未确认时去抖）。返回是否新落一行。"""
    open_row = (
        db.query(SysAlertLog.id)
        .filter(SysAlertLog.rule_key == rule_key, SysAlertLog.acked_at.is_(None))
        .first()
    )
    if open_row is not None:
        return False
    db.add(SysAlertLog(
        rule_key=rule_key, level=level, title=title, content=content, metric=metric,
    ))
    db.commit()
    _logger.warning("alert: %s | %s | metric=%s", rule_key, title, metric)
    return True


def list_alerts(db: Session, *, acked: bool | None = None, level: str | None = None,
                limit: int = 20, offset: int = 0) -> tuple[list[SysAlertLog], int, int]:
    """分页 + 未确认计数（管理端红点）。"""
    q = db.query(SysAlertLog)
    if acked is True:
        q = q.filter(SysAlertLog.acked_at.is_not(None))
    elif acked is False:
        q = q.filter(SysAlertLog.acked_at.is_(None))
    if level:
        q = q.filter(SysAlertLog.level == level)
    total = q.count()
    unacked = (
        db.query(sa.func.count(SysAlertLog.id))
        .filter(SysAlertLog.acked_at.is_(None))
        .scalar() or 0
    )
    rows = q.order_by(SysAlertLog.id.desc()).offset(offset).limit(min(limit, 100)).all()
    return rows, total, int(unacked)


def ack(db: Session, alert_id: int, admin_id: int) -> SysAlertLog:
    row = db.get(SysAlertLog, alert_id)
    if row is None:
        raise AppError(404, "ALERT_NOT_FOUND", "告警不存在")
    if row.acked_at is not None:
        raise AppError(409, "ALERT_STATE", "告警已确认")
    row.acked_by = admin_id
    row.acked_at = dt.datetime.now(dt.UTC)
    db.commit()
    return row


def unacked_count(db: Session) -> int:
    return int(
        db.query(sa.func.count(SysAlertLog.id))
        .filter(SysAlertLog.acked_at.is_(None))
        .scalar() or 0
    )


def critical_unacked_count(db: Session) -> int:
    return int(
        db.query(sa.func.count(SysAlertLog.id))
        .filter(SysAlertLog.acked_at.is_(None), SysAlertLog.level == NoticeLevel.CRITICAL)
        .scalar() or 0
    )
