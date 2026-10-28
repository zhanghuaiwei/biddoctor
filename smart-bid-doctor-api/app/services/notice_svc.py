"""公告通知（sys_notice，05 §3.3）：draft → published（publish_at 生效）→ offline。

用户端仅可见 published 且 publish_at 已到的记录；发布/下线写审计（api 层调用）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.core.enums import NoticeStatus
from app.core.errors import AppError
from app.models import SysNotice


def create(db: Session, *, title: str, content: str, type_: str, level: str,
           publish_at: dt.datetime | None, admin_id: int) -> SysNotice:
    row = SysNotice(
        title=title, content=content, type=type_, level=level,
        publish_at=publish_at, status=NoticeStatus.DRAFT, created_by=admin_id,
    )
    db.add(row)
    db.commit()
    return row


def list_all(db: Session, *, status: str | None = None,
             limit: int = 20, offset: int = 0) -> tuple[list[SysNotice], int]:
    q = db.query(SysNotice).filter(SysNotice.deleted_at.is_(None))
    if status:
        q = q.filter(SysNotice.status == status)
    total = q.count()
    return q.order_by(SysNotice.id.desc()).offset(offset).limit(min(limit, 100)).all(), total


def list_published(db: Session, *, limit: int = 5) -> list[SysNotice]:
    """用户端横幅：published 且 publish_at 已生效，按发布时间倒序。"""
    now = dt.datetime.now(dt.UTC)
    return (
        db.query(SysNotice)
        .filter(
            SysNotice.status == NoticeStatus.PUBLISHED,
            SysNotice.deleted_at.is_(None),
            SysNotice.publish_at.is_not(None),
            SysNotice.publish_at <= now,
        )
        .order_by(SysNotice.publish_at.desc())
        .limit(min(limit, 20))
        .all()
    )


def publish(db: Session, notice_id: int) -> SysNotice:
    row = _get(db, notice_id)
    if row.status != NoticeStatus.DRAFT:
        raise AppError(409, "NOTICE_STATE", f"公告状态为 {row.status}，不可发布")
    row.status = NoticeStatus.PUBLISHED
    row.publish_at = dt.datetime.now(dt.UTC)
    db.commit()
    return row


def offline(db: Session, notice_id: int) -> SysNotice:
    row = _get(db, notice_id)
    if row.status != NoticeStatus.PUBLISHED:
        raise AppError(409, "NOTICE_STATE", f"公告状态为 {row.status}，不可下线")
    row.status = NoticeStatus.OFFLINE
    db.commit()
    return row


def soft_delete(db: Session, notice_id: int) -> None:
    row = _get(db, notice_id)
    if row.status == NoticeStatus.PUBLISHED:
        raise AppError(409, "NOTICE_STATE", "先下线再删除")
    row.deleted_at = dt.datetime.now(dt.UTC)
    db.commit()


def _get(db: Session, notice_id: int) -> SysNotice:
    row = (
        db.query(SysNotice)
        .filter(SysNotice.id == notice_id, SysNotice.deleted_at.is_(None))
        .first()
    )
    if row is None:
        raise AppError(404, "NOTICE_NOT_FOUND", "公告不存在")
    return row
