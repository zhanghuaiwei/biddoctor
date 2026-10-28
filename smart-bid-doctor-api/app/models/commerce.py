"""商业化域模型（P2：支付/订阅/行业包规则库，db DDL §14-18）。

- Payment：渠道支付流水（P2 自助支付预留；当前人工核销不产生记录，表先行落地），
  回调翻转走「原子 UPDATE + rowcount 判定」一次性凭据范式；
- SubscriptionPlan / Subscription：订阅售卖计划与用户订阅实例，下单走 orders 统一
  入口（sku=plan.code），核销时激活并按期发放 quota_accounts(type=sub_<plan>)；
- RuleSet / RuleItem：行业包规则库版本（law_version 新法追踪），注入 extractor
  预筛与 comparator 复核（M2 引擎接入时读取）。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PkMixin, TimestampMixin


class Payment(Base, PkMixin, TimestampMixin):
    """渠道支付流水（P2）：out_trade_no 唯一（幂等键）；callback_raw 留对账凭证。"""

    __tablename__ = "payments"

    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id"))
    channel: Mapped[str] = mapped_column(String(16))  # wechat_native | alipay_qr | wechat_h5
    out_trade_no: Mapped[str] = mapped_column(String(64), unique=True)
    amount_cny: Mapped[float] = mapped_column(Numeric(8, 2))  # Decimal 契约
    status: Mapped[str] = mapped_column(String(16), default="created")
    callback_raw: Mapped[dict | None] = mapped_column(JSONB)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        Index("idx_payments_order", "order_id"),
        Index("idx_payments_status", "status", "created_at"),  # 待对账扫描
    )


class SubscriptionPlan(Base, PkMixin, TimestampMixin):
    """订阅售卖计划：code 即 orders.sku（sub_ 前缀），运营在管理端维护。"""

    __tablename__ = "subscription_plans"

    code: Mapped[str] = mapped_column(String(24), unique=True)  # sub_basic | sub_pro
    name: Mapped[str] = mapped_column(String(64))
    price_cny: Mapped[float] = mapped_column(Numeric(8, 2))  # Decimal 契约
    period_months: Mapped[int] = mapped_column(Integer, default=1)
    compare_quota: Mapped[int] = mapped_column(Integer)  # 每期发放对照次数
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | retired


class Subscription(Base, PkMixin, TimestampMixin):
    """用户订阅实例：激活/续期由订单核销驱动；每期发放一行 quota_accounts。"""

    __tablename__ = "subscriptions"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("subscription_plans.id"))
    order_id: Mapped[int | None] = mapped_column(BigInteger)  # 无 FK（与 comparisons 同口径）
    status: Mapped[str] = mapped_column(String(16), default="active")
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        Index("idx_subs_user", "user_id", "status"),
        Index("idx_subs_renew", "status", "period_end",
              postgresql_where=text("auto_renew = true")),
    )


class RuleSet(Base, PkMixin, TimestampMixin):
    """行业包规则库版本（P2）：同 (industry, law_version, version) 唯一；激活唯一。"""

    __tablename__ = "rule_sets"

    industry: Mapped[str] = mapped_column(String(32))  # general | medical
    law_version: Mapped[str] = mapped_column(String(64))  # 如 tender-law-2027rev
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | active | retired
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("uq_rule_sets", "industry", "law_version", "version", unique=True),)


class RuleItem(Base, PkMixin, TimestampMixin):
    """规则条目：kind 表达式类型 + action 语义（hint/must/veto，02 §4.1）。"""

    __tablename__ = "rule_items"

    rule_set_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("rule_sets.id", ondelete="CASCADE")
    )
    category: Mapped[str] = mapped_column(String(16))  # 五类条款（CheckCategory）
    kind: Mapped[str] = mapped_column(String(16))  # regex | keyword | numeric | date
    pattern: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(String(8), default="hint")
    weight: Mapped[float] = mapped_column(Numeric(3, 2), default=1.00)
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("idx_rule_items_set", "rule_set_id", "category"),)
