"""订单业务（02 §9.5）：人工收款核销流程。api 层只做参数接收与审计留痕。

SKU 两种来源（P2 订阅闭环）：按次包取 FJ_SKU_CATALOG 配置；sub_* 订阅计划取
subscription_plans 表。核销（grant）按 sku 前缀分流：sub_* → 订阅激活 +
按期发放次数包（subscription_svc.activate），其余 → 按次包发放。
"""

import datetime as dt
import random

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import OrderStatus, PlanStatus
from app.core.errors import AppError
from app.models import Order, User
from app.services import quota_svc, subscription_svc

PAY_HINT = "请向收款账户转账并备注订单号，完成后由客服核销开通（人工收款流程）"


def _gen_order_no() -> str:
    # 订单号日期段用北京时间（03：FJ+YYMMDD+6 位随机）——容器 TZ 可能是 UTC，不能用本地时钟
    bj_now = dt.datetime.now(dt.UTC) + dt.timedelta(hours=8)
    return "FJ" + bj_now.strftime("%y%m%d") + f"{random.randint(0, 999999):06d}"


def resolve_amount(db: Session, sku: str) -> float:
    """SKU 金额解析：按次包走配置，sub_* 走订阅计划（停售拒绝下单）。"""
    if sku.startswith("sub_"):
        plan = subscription_svc.get_plan(db, sku)
        if plan is None or plan.status != PlanStatus.ACTIVE:
            raise AppError(400, "BAD_SKU", "订阅计划不存在或已停售")
        return plan.price_cny
    skus = get_settings().skus
    if sku not in skus:
        raise AppError(400, "BAD_SKU", "不存在的商品")
    return skus[sku]["amount_cny"]


def create_order(db: Session, user_id: int, sku: str, note: str | None) -> Order:
    """创建待核销订单：SKU 目录来自配置/计划（单一事实来源），金额 Decimal 落库。

    order_no 撞号走 IntegrityError 重试（唯一约束兜底，最多 3 次）；
    审计留痕（ORDER_CREATED）由 api 层在事务外写，此处不掺审计职责。
    """
    amount = resolve_amount(db, sku)
    # order_no 唯一约束兜底：6 位随机存在撞号概率，冲突重试而非 500（for-else）
    for _ in range(3):
        order = Order(
            order_no=_gen_order_no(),
            user_id=user_id,
            sku=sku,
            amount_cny=amount,
            status=OrderStatus.PENDING,
            note=note,
        )
        db.add(order)
        try:
            db.commit()
            return order
        except sa.exc.IntegrityError:
            db.rollback()
    raise AppError(500, "ORDER_NO_CONFLICT", "订单号生成冲突，请重试")


def list_orders(db: Session, user_id: int, *, limit: int = 20, offset: int = 0) -> tuple[list[Order], int]:
    """本人订单分页（统一 limit/offset，上限 100）。"""
    q = db.query(Order).filter(Order.user_id == user_id)
    total = q.count()
    return (
        q.order_by(Order.id.desc()).offset(offset).limit(min(limit, 100)).all(),
        total,
    )


def list_all_orders(db: Session, *, user_id: int | None = None, status: str | None = None,
                    limit: int = 20, offset: int = 0) -> tuple[list[Order], int]:
    """管理端全量订单分页（含用户/状态筛选）。"""
    q = db.query(Order)
    if user_id is not None:
        q = q.filter(Order.user_id == user_id)
    if status:
        q = q.filter(Order.status == status)
    total = q.count()
    return q.order_by(Order.id.desc()).offset(offset).limit(min(limit, 100)).all(), total


def get_by_order_no(db: Session, order_no: str) -> Order | None:
    """按订单号查单（核销入口用；None 语义由 api 层转 404）。"""
    return db.query(Order).filter(Order.order_no == order_no).first()


def grant(db: Session, admin: User, order: Order) -> None:
    """核销：订单状态翻转 + 发放同一事务（半失败即整体回滚）。

    sub_* 订单走订阅激活（激活/续期 + 当期次数包同事务）；其余按次包发放。
    """
    if order.status != OrderStatus.PENDING:
        raise AppError(409, "ORDER_STATE", f"订单状态为 {order.status}，不可核销")
    order.status = OrderStatus.GRANTED
    order.granted_at = dt.datetime.now(dt.UTC)
    order.granted_by = admin.id
    if order.sku.startswith("sub_"):
        subscription_svc.activate(db, order)
        db.commit()
    else:
        quota_svc.grant_pack(db, order.user_id, order.sku, source_order=order.id)
        db.commit()
