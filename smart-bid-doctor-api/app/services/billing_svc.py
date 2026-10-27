"""订单业务（02 §9.5）：人工收款核销流程。api 层只做参数接收与审计留痕。"""

import datetime as dt
import random

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Order, User
from app.services import quota_svc

PAY_HINT = "请向收款账户转账并备注订单号，完成后由客服核销开通（人工收款流程）"


def _gen_order_no() -> str:
    # 订单号日期段用北京时间（03：FJ+YYMMDD+6 位随机）——容器 TZ 可能是 UTC，不能用本地时钟
    bj_now = dt.datetime.now(dt.UTC) + dt.timedelta(hours=8)
    return "FJ" + bj_now.strftime("%y%m%d") + f"{random.randint(0, 999999):06d}"


def create_order(db: Session, user_id: int, sku: str, note: str | None) -> Order:
    skus = get_settings().skus
    if sku not in skus:
        raise AppError(400, "BAD_SKU", "不存在的商品")
    # order_no 唯一约束兜底：6 位随机存在撞号概率，冲突重试而非 500（for-else）
    for _ in range(3):
        order = Order(
            order_no=_gen_order_no(),
            user_id=user_id,
            sku=sku,
            amount_cny=skus[sku]["amount_cny"],
            status="pending",
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
    q = db.query(Order).filter(Order.user_id == user_id)
    total = q.count()
    return (
        q.order_by(Order.id.desc()).offset(offset).limit(min(limit, 100)).all(),
        total,
    )


def get_by_order_no(db: Session, order_no: str) -> Order | None:
    return db.query(Order).filter(Order.order_no == order_no).first()


def grant(db: Session, admin: User, order: Order) -> None:
    """核销：订单状态 + 发放次数包同一事务（半失败即整体回滚）"""
    if order.status != "pending":
        raise AppError(409, "ORDER_STATE", f"订单状态为 {order.status}，不可核销")
    order.status = "granted"
    order.granted_at = dt.datetime.now(dt.UTC)
    order.granted_by = admin.id
    quota_svc.grant_pack(db, order.user_id, order.sku, source_order=order.id)
    db.commit()
