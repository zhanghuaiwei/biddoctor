"""用户端平台端点：当前用户导航（me）+ 公告横幅 + 附件 + 法务签署。

- /me/menus：管理端导航数据（菜单树 + 权限点集合，非 admin 返回空集）；
- /notices、/legal/current：公开只读（站点横幅/协议展示）；
- /legal/agreements：签署留痕（PIPL「告知-同意」，登录态 + IP 记录）；
- /attachments：通用附件上传/下载/删除（≤20MB 白名单，凭证等场景）。
"""

import datetime as dt
import os

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import client_ip, get_current_user
from app.core.errors import ERROR_CODES, AppError
from app.models import Order, SysNotice, User
from app.schemas.platform import AttachmentOut, LegalCurrentOut, LegalDocOut, MeMenusOut
from app.services import attachment_svc, audit_svc, legal_svc, rbac_svc

router = APIRouter(tags=["me-platform"])

A = audit_svc.AuditAction


@router.get("/me/menus", response_model=MeMenusOut)
def my_menus(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """管理端导航数据：菜单树 + 权限点集合（非 admin 返回空集，前端不渲染入口）。"""
    perms = rbac_svc.perm_set(db, user)
    menus = rbac_svc.menu_tree(db, perms) if perms else []
    return MeMenusOut(menus=menus, perms=sorted(perms))


@router.get("/notices", response_model=list[dict])
def published_notices(
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """用户端公告横幅：已发布且 publish_at 生效的记录（公开，无需登录）。"""
    now = dt.datetime.now(dt.UTC)
    rows = (
        db.query(SysNotice)
        .filter(
            SysNotice.status == "published",
            SysNotice.deleted_at.is_(None),
            SysNotice.publish_at.is_not(None),
            SysNotice.publish_at <= now,
        )
        .order_by(SysNotice.publish_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {"id": n.id, "title": n.title, "content": n.content,
         "type": n.type, "level": n.level, "publish_at": n.publish_at}
        for n in rows
    ]


# ── 法务（05 §8）─────────────────────────────────────────────────────────────


@router.get("/legal/current", response_model=LegalCurrentOut)
def current_legal(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """三类法务文档当前生效版 + 本人已签署版本（登录后强制签署弹层数据源）。"""
    return _current(user, db)


def _current(user: User, db: Session) -> LegalCurrentOut:
    docs = legal_svc.current_all(db)
    signed = legal_svc.signed_doc_ids(db, user.id)
    return LegalCurrentOut(
        documents=[LegalDocOut.model_validate(d) for d in docs],
        signed_ids=sorted(signed),
    )


@router.post("/legal/agreements", response_model=LegalCurrentOut)
def sign_agreements(
    request: Request,
    legal_doc_ids: list[int],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """批量签署当前生效文档（登录首次勾选/新版本再确认均走此入口）。"""
    ip = client_ip(request)
    for doc_id in legal_doc_ids:
        legal_svc.sign(db, user_id=user.id, doc_id=doc_id, ip=ip)
    audit_svc.log(
        db, user.id, A.AGREEMENT_SIGNED, target=f"user:{user.id}",
        detail={"legal_doc_ids": legal_doc_ids}, ip=ip,
    )
    return _current(user, db)


# ── 附件（05 §7：凭证截图等；documents 标书原件走 projects 上传，不在此）──────


@router.post("/attachments", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    request: Request,
    file: UploadFile = File(...),
    module: str = Form(...),
    business_id: int | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """通用附件上传（≤20MB，白名单类型）。order_voucher 需归属本人订单。"""
    if module == "order_voucher":
        if business_id is None:
            raise AppError(ERROR_CODES["VALIDATION_ERROR"], "VALIDATION_ERROR", "缺少关联订单")
        order = (
            db.query(Order)
            .filter(Order.id == business_id, Order.user_id == user.id)
            .first()
        )
        if order is None:
            raise AppError(404, "ORDER_NOT_FOUND", "订单不存在")
    row = attachment_svc.upload(
        db, module=module, business_id=business_id, file=file, user_id=user.id,
    )
    audit_svc.log(db, user.id, A.ATTACHMENT_UPLOAD,
                  target=f"attachment:{row.id}",
                  detail={"module": module, "business_id": business_id},
                  ip=client_ip(request))
    return row


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """归属校验后流式下载（本人上传的，或本人订单下的凭证）。"""
    row = attachment_svc.owned_attachment(db, attachment_id, user.id)
    if not os.path.exists(row.stored_path):
        raise AppError(404, "ATTACHMENT_NOT_FOUND", "附件文件已清理")
    return FileResponse(
        row.stored_path,
        filename=row.orig_name,
        media_type=row.content_type or "application/octet-stream",
    )


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = attachment_svc.owned_attachment(db, attachment_id, user.id)
    attachment_svc.soft_delete(db, row)
    audit_svc.log(db, user.id, A.ATTACHMENT_DELETE, target=f"attachment:{attachment_id}")
