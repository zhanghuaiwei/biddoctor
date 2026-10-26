import datetime as dt
import random

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user, require_admin
from app.core.errors import AppError
from app.models import Order, User
from app.schemas.billing import GrantOut, OrderIn, OrderOut, OrderPage, QuotaOut
from app.services import audit_svc, quota_svc

router = APIRouter(tags=["billing"])

PAY_HINT = "请向收款账户转账并备注订单号，完成后由客服核销开通（人工收款流程）"


@router.get("/me/quota", response_model=QuotaOut)
def my_quota(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return QuotaOut(free_left=quota_svc.free_left(db, user.id), packs=quota_svc.packs(db, user.id))


def _gen_order_no() -> str:
    return "FJ" + dt.datetime.now().strftime("%y%m%d") + f"{random.randint(0, 999999):06d}"


@router.post("/orders", response_model=OrderOut, status_code=201)  # 02 §9.5 路径
def create_order(body: OrderIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    skus = get_settings().skus
    if body.sku not in skus:
        raise AppError(400, "BAD_SKU", "不存在的商品")
    # order_no 唯一约束兜底：6 位随机存在撞号概率，冲突重试而非 500（for-else）
    for _ in range(3):
        order = Order(
            order_no=_gen_order_no(),
            user_id=user.id,
            sku=body.sku,
            amount_cny=skus[body.sku]["amount_cny"],
            status="pending",
            note=body.note,
        )
        db.add(order)
        try:
            db.commit()
            break
        except sa.exc.IntegrityError:
            db.rollback()
    else:
        raise AppError(500, "ORDER_NO_CONFLICT", "订单号生成冲突，请重试")
    audit_svc.log(
        db, user.id, "order_created", target=order.order_no,
        detail={"sku": order.sku, "amount_cny": str(order.amount_cny)},
    )
    out = OrderOut.model_validate(order)
    out.pay_hint = PAY_HINT
    return out


@router.get("/orders", response_model=OrderPage)
def my_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Order)
        .filter(Order.user_id == user.id)
        .order_by(Order.id.desc())
        .limit(50)
        .all()
    )
    return OrderPage(items=[OrderOut.model_validate(o) for o in rows])


@router.post("/admin/orders/{order_no}/grant", response_model=GrantOut)
def grant_order(
    order_no: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """核销：订单状态 + 发放次数包同一事务（半失败即整体回滚）"""
    order = db.query(Order).filter(Order.order_no == order_no).first()
    if order is None:
        raise AppError(404, "ORDER_NOT_FOUND", "订单不存在")
    if order.status != "pending":
        raise AppError(409, "ORDER_STATE", f"订单状态为 {order.status}，不可核销")

    order.status = "granted"
    order.granted_at = dt.datetime.now(dt.UTC)
    order.granted_by = admin.id
    quota_svc.grant_pack(db, order.user_id, order.sku, source_order=order.id)
    db.commit()

    audit_svc.log(db, admin.id, "order_grant", target=order.order_no, detail={"user_id": order.user_id})
    return GrantOut(order_no=order.order_no, status="granted")
