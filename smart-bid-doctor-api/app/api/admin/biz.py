"""业务运营端点（05 §10）：订单 / 附件 / 法务 / AI 治理 / 订阅 / 规则库 / 支付流水。

权限点：admin:order:read | admin:order:grant | admin:attachment | admin:legal |
admin:ai | admin:sub | admin:rule。AI/法务/订阅/规则库管理动作写审计（05 §5.2）。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_perm
from app.core.errors import ERROR_CODES, AppError
from app.models import Payment, SubscriptionPlan, User
from app.schemas.billing import GrantOut, OrderOut
from app.schemas.platform import (
    AiModelIn,
    AiModelOut,
    AiModelUpdate,
    AttachmentOut,
    AttachmentPage,
    LegalDocIn,
    LegalDocOut,
    OkOut,
    PaymentPage,
    PlanIn,
    PlanOut,
    PlanUpdate,
    PromptIn,
    PromptOut,
    RuleItemIn,
    RuleItemOut,
    RuleSetIn,
    RuleSetOut,
    SignatureOut,
    SignaturePage,
    SubscriptionOut,
    SubscriptionPage,
)
from app.services import (
    ai_svc,
    audit_svc,
    billing_svc,
    legal_svc,
    rule_svc,
    subscription_svc,
)

router = APIRouter(tags=["admin-biz"])

A = audit_svc.AuditAction


# ── 订单管理 ─────────────────────────────────────────────────────────────────


@router.get("/orders", response_model=list[OrderOut])
def admin_orders(
    user_id: int | None = None,
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:order:read")),
    db: Session = Depends(get_db),
):
    rows, _total = billing_svc.list_all_orders(
        db, user_id=user_id, status=status, limit=limit, offset=offset,
    )
    return [OrderOut.model_validate(o) for o in rows]


@router.post("/orders/{order_no}/grant", response_model=GrantOut)
def grant_order(
    order_no: str,
    admin: User = Depends(require_perm("admin:order:grant")),
    db: Session = Depends(get_db),
):
    """核销（订单号路径，与 v1 POST /admin/orders/{order_no}/grant 同语义归口此处）。"""
    order = billing_svc.get_by_order_no(db, order_no)
    if order is None:
        raise AppError(ERROR_CODES["ORDER_NOT_FOUND"], "ORDER_NOT_FOUND", "订单不存在")
    is_sub = order.sku.startswith("sub_")
    billing_svc.grant(db, admin, order)
    audit_svc.log(
        db, admin.id,
        A.SUBSCRIPTION_GRANT if is_sub else A.ORDER_GRANT,
        target=order.order_no, detail={"user_id": order.user_id, "sku": order.sku},
    )
    return GrantOut(order_no=order.order_no, status="granted")


# ── 附件管理（05 §7）─────────────────────────────────────────────────────────


@router.get("/attachments", response_model=AttachmentPage)
def admin_attachments(
    module: str | None = None,
    business_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:attachment")),
    db: Session = Depends(get_db),
):
    from app.services import attachment_svc

    rows, total = attachment_svc.list_all(db, module=module, business_id=business_id,
                                          limit=limit, offset=offset)
    return AttachmentPage(items=[AttachmentOut.model_validate(a) for a in rows], total=total)


@router.delete("/attachments/{attachment_id}", response_model=OkOut)
def admin_delete_attachment(
    attachment_id: int,
    admin: User = Depends(require_perm("admin:attachment")),
    db: Session = Depends(get_db),
):
    from app.services import attachment_svc

    row = attachment_svc.get_for_admin(db, attachment_id)
    attachment_svc.soft_delete(db, row)
    audit_svc.log(db, admin.id, A.ATTACHMENT_DELETE, target=f"attachment:{attachment_id}")
    return OkOut()


# ── 法务文档（05 §8）─────────────────────────────────────────────────────────


@router.get("/legal/documents", response_model=list[LegalDocOut])
def admin_legal(_: User = Depends(require_perm("admin:legal")), db: Session = Depends(get_db)):
    return legal_svc.list_all(db)


@router.post("/legal/documents", response_model=LegalDocOut, status_code=201)
def create_legal(
    body: LegalDocIn,
    admin: User = Depends(require_perm("admin:legal")),
    db: Session = Depends(get_db),
):
    row = legal_svc.create(
        db, doc_type=body.doc_type, version=body.version, title=body.title,
        content=body.content, effective_at=body.effective_at,
    )
    return row


@router.post("/legal/documents/{doc_id}/publish", response_model=LegalDocOut)
def publish_legal(
    doc_id: int,
    admin: User = Depends(require_perm("admin:legal")),
    db: Session = Depends(get_db),
):
    row = legal_svc.publish(db, doc_id)
    audit_svc.log(db, admin.id, A.LEGAL_PUBLISH,
                  target=f"legal:{row.doc_type}:{row.version}")
    return row


@router.post("/legal/documents/{doc_id}/retire", response_model=LegalDocOut)
def retire_legal(
    doc_id: int,
    admin: User = Depends(require_perm("admin:legal")),
    db: Session = Depends(get_db),
):
    return legal_svc.retire(db, doc_id)


@router.get("/legal/signatures", response_model=SignaturePage)
def legal_signatures(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:legal")),
    db: Session = Depends(get_db),
):
    rows, total = legal_svc.list_signatures(db, limit=limit, offset=offset)
    emails = {
        u.id: u.email
        for u in db.query(User).filter(
            User.id.in_({r.user_id for r in rows} or {0})).all()
    }
    items = [
        SignatureOut.model_validate(r).model_copy(update={"user_email": emails.get(r.user_id)})
        for r in rows
    ]
    return SignaturePage(items=items, total=total)


# ── AI 治理（05 §9）──────────────────────────────────────────────────────────


@router.get("/ai/models", response_model=list[AiModelOut])
def list_ai_models(_: User = Depends(require_perm("admin:ai")), db: Session = Depends(get_db)):
    return ai_svc.list_models(db)


@router.post("/ai/models", response_model=AiModelOut, status_code=201)
def create_ai_model(
    body: AiModelIn,
    admin: User = Depends(require_perm("admin:ai")),
    db: Session = Depends(get_db),
):
    row = ai_svc.create_model(db, **body.model_dump())
    audit_svc.log(db, admin.id, A.AI_MODEL_UPDATE, target=f"ai-model:{row.model_code}",
                  detail={"op": "create"})
    return row


@router.patch("/ai/models/{model_id}", response_model=AiModelOut)
def update_ai_model(
    model_id: int, body: AiModelUpdate,
    admin: User = Depends(require_perm("admin:ai")),
    db: Session = Depends(get_db),
):
    fields = body.model_dump(exclude_unset=True)
    row = ai_svc.update_model(db, model_id, **fields)
    audit_svc.log(db, admin.id, A.AI_MODEL_UPDATE, target=f"ai-model:{row.model_code}",
                  detail={"fields": sorted(fields)})
    return row


@router.get("/ai/prompts", response_model=list[PromptOut])
def list_prompts(
    purpose: str | None = None,
    _: User = Depends(require_perm("admin:ai")),
    db: Session = Depends(get_db),
):
    return ai_svc.list_prompts(db, purpose=purpose)


@router.post("/ai/prompts", response_model=PromptOut, status_code=201)
def create_prompt(
    body: PromptIn,
    admin: User = Depends(require_perm("admin:ai")),
    db: Session = Depends(get_db),
):
    row = ai_svc.create_prompt(
        db, name=body.name, purpose=body.purpose, version=body.version,
        template=body.template, variables=body.variables,
    )
    audit_svc.log(db, admin.id, A.AI_PROMPT_PUBLISH, target=f"prompt:{row.name}:v{row.version}")
    return row


@router.post("/ai/prompts/{prompt_id}/activate", response_model=PromptOut)
def activate_prompt(
    prompt_id: int,
    admin: User = Depends(require_perm("admin:ai")),
    db: Session = Depends(get_db),
):
    row = ai_svc.activate_prompt(db, prompt_id, admin.id)
    audit_svc.log(db, admin.id, A.AI_PROMPT_SWITCH,
                  target=f"prompt:{row.name}:v{row.version}",
                  detail={"eval_score": row.eval_score})
    return row


# ── 订阅管理（P2）────────────────────────────────────────────────────────────


@router.get("/subs/plans", response_model=list[PlanOut])
def list_plans(_: User = Depends(require_perm("admin:sub")), db: Session = Depends(get_db)):
    return subscription_svc.list_plans(db)


@router.post("/subs/plans", response_model=PlanOut, status_code=201)
def create_plan(
    body: PlanIn,
    admin: User = Depends(require_perm("admin:sub")),
    db: Session = Depends(get_db),
):
    return subscription_svc.create_plan(
        db, code=body.code, name=body.name, price_cny=float(body.price_cny),
        period_months=body.period_months, compare_quota=body.compare_quota,
    )


@router.patch("/subs/plans/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: int, body: PlanUpdate,
    admin: User = Depends(require_perm("admin:sub")),
    db: Session = Depends(get_db),
):
    return subscription_svc.update_plan(
        db, plan_id, name=body.name,
        price_cny=float(body.price_cny) if body.price_cny is not None else None,
        status=body.status,
    )


@router.get("/subs", response_model=SubscriptionPage)
def list_subscriptions(
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:sub")),
    db: Session = Depends(get_db),
):
    rows, total = subscription_svc.list_all(db, status=status, limit=limit, offset=offset)
    plan_codes = {
        p.id: p.code
        for p in db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id.in_({r.plan_id for r in rows} or {0})
        ).all()
    } if rows else {}
    emails = subscription_svc.user_email_map(db, [r.user_id for r in rows])
    items = [
        SubscriptionOut.model_validate(r).model_copy(update={
            "user_email": emails.get(r.user_id), "plan_code": plan_codes.get(r.plan_id),
        })
        for r in rows
    ]
    return SubscriptionPage(items=items, total=total)


# ── 规则库（P2 行业包）───────────────────────────────────────────────────────


@router.get("/rules/sets", response_model=list[RuleSetOut])
def list_rule_sets(
    industry: str | None = None,
    _: User = Depends(require_perm("admin:rule")),
    db: Session = Depends(get_db),
):
    return rule_svc.list_sets(db, industry=industry)


@router.post("/rules/sets", response_model=RuleSetOut, status_code=201)
def create_rule_set(
    body: RuleSetIn,
    admin: User = Depends(require_perm("admin:rule")),
    db: Session = Depends(get_db),
):
    row = rule_svc.create_set(db, industry=body.industry,
                              law_version=body.law_version, notes=body.notes)
    audit_svc.log(db, admin.id, A.RULESET_UPDATE, target=f"ruleset:{row.id}",
                  detail={"op": "create"})
    return row


@router.post("/rules/sets/{set_id}/activate", response_model=RuleSetOut)
def activate_rule_set(
    set_id: int,
    admin: User = Depends(require_perm("admin:rule")),
    db: Session = Depends(get_db),
):
    row = rule_svc.activate_set(db, set_id)
    audit_svc.log(db, admin.id, A.RULESET_UPDATE, target=f"ruleset:{row.id}",
                  detail={"op": "activate"})
    return row


@router.post("/rules/sets/{set_id}/retire", response_model=RuleSetOut)
def retire_rule_set(
    set_id: int,
    admin: User = Depends(require_perm("admin:rule")),
    db: Session = Depends(get_db),
):
    return rule_svc.retire_set(db, set_id)


@router.get("/rules/sets/{set_id}/items", response_model=list[RuleItemOut])
def list_rule_items(
    set_id: int,
    _: User = Depends(require_perm("admin:rule")),
    db: Session = Depends(get_db),
):
    return rule_svc.list_items(db, set_id)


@router.post("/rules/sets/{set_id}/items", response_model=RuleItemOut, status_code=201)
def add_rule_item(
    set_id: int, body: RuleItemIn,
    admin: User = Depends(require_perm("admin:rule")),
    db: Session = Depends(get_db),
):
    return rule_svc.add_item(
        db, set_id, category=body.category, kind=body.kind, pattern=body.pattern,
        action=body.action, weight=float(body.weight), description=body.description,
    )


@router.delete("/rules/items/{item_id}", response_model=OkOut)
def delete_rule_item(
    item_id: int,
    admin: User = Depends(require_perm("admin:rule")),
    db: Session = Depends(get_db),
):
    rule_svc.delete_item(db, item_id)
    audit_svc.log(db, admin.id, A.RULESET_UPDATE, target=f"rule-item:{item_id}",
                  detail={"op": "delete"})
    return OkOut()


# ── 支付流水（P2 预留，只读对账视图）────────────────────────────────────────


@router.get("/payments", response_model=PaymentPage)
def list_payments(
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:order:read")),
    db: Session = Depends(get_db),
):
    q = db.query(Payment)
    if status:
        q = q.filter(Payment.status == status)
    total = q.count()
    rows = q.order_by(Payment.id.desc()).offset(offset).limit(min(limit, 100)).all()
    return PaymentPage(items=rows, total=total)


@router.get("/attachments/{attachment_id}", response_model=AttachmentOut)
def admin_attachment_detail(
    attachment_id: int,
    _: User = Depends(require_perm("admin:attachment")),
    db: Session = Depends(get_db),
):
    from app.services import attachment_svc

    row = attachment_svc.get_for_admin(db, attachment_id)
    return AttachmentOut.model_validate(row)
