"""配额与订单（03 §2.10–2.11 quota_accounts / orders）。

- QuotaAccount：对照次数包（remain 原子扣减见 quota_svc.consume_compare；
  免费额度走月度计数不入此表）；source_order 溯源但不加 FK（保留人工调整余地）；
- Order：人工收款核销流程——order_no 唯一（FJ+北京日期+6 位随机，撞号重试），
  状态机 pending → granted / expired / refunded，金额 Numeric(8,2) Decimal 契约。
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PkMixin, TimestampMixin


class QuotaAccount(Base, PkMixin, TimestampMixin):
    __tablename__ = "quota_accounts"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(16))  # cmp_x5 | cmp_x20（free 走月度计数，不入此表）
    remain: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_order: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (Index("idx_quota_user", "user_id", "expires_at"),)


class Order(Base, PkMixin, TimestampMixin):
    __tablename__ = "orders"

    order_no: Mapped[str] = mapped_column(String(24), unique=True)  # FJ+YYMMDD+6位随机
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    sku: Mapped[str] = mapped_column(String(16))  # cmp_x5 | cmp_x20
    amount_cny: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending | granted | expired | refunded
    note: Mapped[str | None] = mapped_column(String(256))
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    granted_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))

    __table_args__ = (Index("idx_orders_user", "user_id", "created_at"),)
