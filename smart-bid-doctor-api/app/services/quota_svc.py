"""对照次数包：原子扣减 / 发放。commit 由调用方负责（保证与业务同事务）。"""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Project, QuotaAccount


def free_left(db: Session, user_id: int) -> int:
    s = get_settings()
    month_start = dt.datetime.now(dt.UTC).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    used = (
        db.query(sa.func.count(Project.id))
        .filter(
            Project.user_id == user_id,
            Project.created_at >= month_start,
            # 注意：不排除 deleted_at——软删项目仍计入当月已用，防"建→删→重建"刷免费解析
        )
        .scalar()
        or 0
    )
    return max(0, s.free_projects_per_month - used)


def packs(db: Session, user_id: int) -> list[QuotaAccount]:
    """有效次数包（未过期且有剩余）。返回 ORM 行，schema 层负责序列化。"""
    now = dt.datetime.now(dt.UTC)
    rows = (
        db.query(QuotaAccount)
        .filter(
            QuotaAccount.user_id == user_id,
            sa.or_(QuotaAccount.expires_at.is_(None), QuotaAccount.expires_at > now),
        )
        .order_by(QuotaAccount.id.asc())
        .all()
    )
    return [r for r in rows if int(r.remain) > 0]


def consume_compare(db: Session, user_id: int) -> int | None:
    """原子扣减一次对照次数，返回消耗的 quota id；无可用次数返回 None。不 commit。

    单条 UPDATE 原子消费：未命中（rowcount=0）即无任何副作用，调用方无需回滚。
    """
    now = dt.datetime.now(dt.UTC)
    return db.execute(
        sa.update(QuotaAccount)
        .where(
            QuotaAccount.user_id == user_id,
            QuotaAccount.remain > 0,
            sa.or_(QuotaAccount.expires_at.is_(None), QuotaAccount.expires_at > now),
        )
        .values(remain=QuotaAccount.remain - 1)
        .returning(QuotaAccount.id)
    ).scalar()


def grant_pack(db: Session, user_id: int, sku: str, source_order: int | None, days_valid: int = 180):
    q = QuotaAccount(
        user_id=user_id,
        type=sku,
        remain=int(sku.rsplit("_x", 1)[1]),
        expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(days=days_valid),
        source_order=source_order,
    )
    db.add(q)
    return q
