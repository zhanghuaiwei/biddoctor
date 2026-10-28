"""订阅制（subscription_plans / subscriptions，P2，05 商业化）。

闭环：管理端配计划（code=sub_*）→ 用户端下单（orders 统一入口）→ 管理员核销
→ billing_svc.grant 分流到 subscription_svc.activate：激活/续期订阅实例 +
按期发放 quota_accounts(type=sub_<plan>, expires_at=period_end)，与按次包同机制消费。
到期清理（expired 置位）由 stats_rollup job 顺带扫描。
"""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.enums import PlanStatus, SubscriptionStatus
from app.core.errors import AppError
from app.models import Order, QuotaAccount, Subscription, SubscriptionPlan, User


def list_plans(db: Session, *, only_active: bool = False) -> list[SubscriptionPlan]:
    q = db.query(SubscriptionPlan)
    if only_active:
        q = q.filter(SubscriptionPlan.status == PlanStatus.ACTIVE)
    return q.order_by(SubscriptionPlan.price_cny.asc()).all()


def get_plan(db: Session, code: str) -> SubscriptionPlan | None:
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.code == code).first()


def create_plan(db: Session, *, code: str, name: str, price_cny: float,
                period_months: int, compare_quota: int) -> SubscriptionPlan:
    if not code.startswith("sub_"):
        raise AppError(400, "BAD_SKU", "订阅计划编码必须以 sub_ 开头")
    if db.query(SubscriptionPlan.id).filter(SubscriptionPlan.code == code).first():
        raise AppError(409, "PLAN_STATE", "计划编码已存在")
    row = SubscriptionPlan(
        code=code, name=name, price_cny=price_cny,
        period_months=max(1, period_months), compare_quota=max(0, compare_quota),
        status=PlanStatus.ACTIVE,
    )
    db.add(row)
    db.commit()
    return row


def update_plan(db: Session, plan_id: int, *, name: str | None, price_cny: float | None,
                status: str | None) -> SubscriptionPlan:
    row = db.get(SubscriptionPlan, plan_id)
    if row is None:
        raise AppError(404, "PLAN_NOT_FOUND", "订阅计划不存在")
    for k, v in (("name", name), ("price_cny", price_cny), ("status", status)):
        if v is not None:
            setattr(row, k, v)
    db.commit()
    return row


def activate(db: Session, order: Order) -> Subscription:
    """核销分流（billing_svc.grant 调用）：激活/续期 + 发放当期次数，同事务只 add/flush。

    续期：存在 active 同计划订阅则 period_end 顺延一期；否则新实例。
    """
    plan = get_plan(db, order.sku)
    if plan is None or plan.status != PlanStatus.ACTIVE:
        raise AppError(400, "BAD_SKU", "订阅计划不存在或已停售")
    now = dt.datetime.now(dt.UTC)
    sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == order.user_id,
                Subscription.plan_id == plan.id,
                Subscription.status == SubscriptionStatus.ACTIVE)
        .first()
    )
    period_start = sub.period_end if sub else now
    period_end = period_start + dt.timedelta(days=30 * plan.period_months)
    if sub is None:
        sub = Subscription(
            user_id=order.user_id, plan_id=plan.id, order_id=order.id,
            status=SubscriptionStatus.ACTIVE,
            period_start=period_start, period_end=period_end,
        )
        db.add(sub)
        db.flush()
    else:
        sub.order_id = order.id
        sub.period_end = period_end
    db.add(QuotaAccount(
        user_id=order.user_id,
        type=f"sub_{plan.code.removeprefix('sub_')}",
        remain=plan.compare_quota,
        expires_at=period_end,  # 订阅发放行 = 当期 period_end（db DDL §12）
        source_order=order.id,
    ))
    return sub


def my_subscriptions(db: Session, user_id: int) -> list[Subscription]:
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.id.desc())
        .all()
    )


def list_all(db: Session, *, status: str | None = None,
             limit: int = 20, offset: int = 0) -> tuple[list[Subscription], int]:
    q = db.query(Subscription)
    if status:
        q = q.filter(Subscription.status == status)
    total = q.count()
    return q.order_by(Subscription.id.desc()).offset(offset).limit(min(limit, 100)).all(), total


def sweep_expired(db: Session) -> int:
    """到期订阅置 expired（stats_rollup 每日顺带调用；auto_renew 续费依赖 P2 支付）。"""
    now = dt.datetime.now(dt.UTC)
    res = db.execute(
        sa.update(Subscription)
        .where(Subscription.status == SubscriptionStatus.ACTIVE,
               Subscription.period_end < now)
        .values(status=SubscriptionStatus.EXPIRED, updated_at=now)
    )
    db.commit()
    return int(res.rowcount)


def user_email_map(db: Session, user_ids: list[int]) -> dict[int, str]:
    rows = db.query(User.id, User.email).filter(User.id.in_(set(user_ids))).all()
    return {r[0]: r[1] for r in rows}
