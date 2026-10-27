from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_admin
from app.core.errors import ERROR_CODES, AppError
from app.models import User
from app.schemas.billing import GrantOut, OrderIn, OrderOut, OrderPage, QuotaOut, QuotaPackOut
from app.services import audit_svc, billing_svc, quota_svc

router = APIRouter(tags=["billing"])


@router.get("/me/quota", response_model=QuotaOut)
def my_quota(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return QuotaOut(
        free_left=quota_svc.free_left(db, user.id),
        packs=[QuotaPackOut.model_validate(p) for p in quota_svc.packs(db, user.id)],
    )


@router.post("/orders", response_model=OrderOut, status_code=201)  # 02 §9.5 路径
def create_order(body: OrderIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = billing_svc.create_order(db, user.id, sku=body.sku, note=body.note)
    audit_svc.log(
        db, user.id, audit_svc.AuditAction.ORDER_CREATED, target=order.order_no,
        detail={"sku": order.sku, "amount_cny": str(order.amount_cny)},
    )
    # 收款提示仅在下单响应返回（02 §9.5：页面展示收款码+订单号）
    return OrderOut.model_validate(order).model_copy(update={"pay_hint": billing_svc.PAY_HINT})


@router.get("/orders", response_model=OrderPage)
def my_orders(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows, total = billing_svc.list_orders(db, user.id, limit=limit, offset=offset)
    return OrderPage(items=[OrderOut.model_validate(o) for o in rows], total=total)


@router.post("/admin/orders/{order_no}/grant", response_model=GrantOut)
def grant_order(
    order_no: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    order = billing_svc.get_by_order_no(db, order_no)
    if order is None:
        raise AppError(ERROR_CODES["ORDER_NOT_FOUND"], "ORDER_NOT_FOUND", "订单不存在")
    billing_svc.grant(db, admin, order)
    audit_svc.log(
        db, admin.id, audit_svc.AuditAction.ORDER_GRANT,
        target=order.order_no, detail={"user_id": order.user_id},
    )
    return GrantOut(order_no=order.order_no, status="granted")
