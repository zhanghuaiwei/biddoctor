"""配额 / 订单接口（02 §9.5）：次数包购买（人工核销）与免费额度查询。

流程：用户下单（pending，返回 PAY_HINT 收款提示）→ 线下转账 → 管理员核销（grant，
订单状态 + 发放次数包同一事务）→ `quota_accounts.remain` 增加。
金额一律 Decimal（JSON 输出字符串）；下单与核销均写审计留痕。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.billing import OrderIn, OrderOut, OrderPage, QuotaOut, QuotaPackOut
from app.schemas.platform import PlanOut
from app.services import audit_svc, billing_svc, quota_svc, subscription_svc

router = APIRouter(tags=["billing"])


@router.get("/me/quota", response_model=QuotaOut)
def my_quota(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return QuotaOut(
        free_left=quota_svc.free_left(db, user.id),
        packs=[QuotaPackOut.model_validate(p) for p in quota_svc.packs(db, user.id)],
    )


@router.get("/subs/plans", response_model=list[PlanOut])
def list_active_plans(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """用户端订阅计划（仅 active 在售；管理端全量走 /admin/subs/plans）。"""
    return subscription_svc.list_plans(db, only_active=True)


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

# 核销端点归口管理端：POST /api/admin/orders/{order_no}/grant（app/api/admin/biz.py，
# 权限点 admin:order:grant，05 §10）——v1 的 require_admin 版本并入，路径/语义不变
