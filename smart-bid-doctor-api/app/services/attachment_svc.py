"""附件管理（attachments，05 §7）：通用附件上传/下载/软删。

- module 白名单（AttachmentModule）+ 类型白名单（图片/PDF/Office 常规）+ 单文件 ≤20MB；
- 流式接收边算 sha256（与 documents 同范式，禁整文件进内存）；
- sha256 去重存储：/data/attachments/<年月>/<sha256><ext>（年月取北京时间）；
- 下载走归属校验后 FileResponse；删除=软删，物理文件随 purge 按引用计数回收。
"""

import datetime as dt
import hashlib
import os
import tempfile
from typing import BinaryIO

import sqlalchemy as sa
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import AttachmentModule
from app.core.errors import AppError
from app.models import Attachment, Order

_MAX_MB = 20
_SPOOL_MEM_BYTES = 4 * 1024 * 1024
_CHUNK_BYTES = 1024 * 1024

# 魔数白名单（图片/PDF/Office 常规格式）
_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"%PDF", "pdf"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF8", "gif"),
)
_ZIP_MAGIC = b"PK\x03\x04"  # docx/xlsx/pptx（OOXML）
_OLE_MAGIC = b"\xd0\xcf\x11\xe0"  # doc/xls/ppt（97-2003）

_ALLOWED_EXTS = {
    "pdf", "png", "jpg", "jpeg", "gif", "webp",
    "doc", "docx", "xls", "xlsx", "ppt", "pptx",
}
_ZIP_EXTS = {"docx", "xlsx", "pptx"}
_OLE_EXTS = {"doc", "xls", "ppt"}


def _sniff_magic(head: bytes) -> str | None:
    for magic, ext in _MAGIC:
        if head.startswith(magic):
            return ext
    if head.startswith(_ZIP_MAGIC):
        return "zip"  # OOXML 容器，具体类型以扩展名为准
    if head.startswith(_OLE_MAGIC):
        return "ole"
    return None


def _check(file: UploadFile, spool: BinaryIO) -> tuple[int, str, str]:
    """大小/魔数/扩展名校验，返回 (size, sha256, ext)。"""
    limit = _MAX_MB * 1024 * 1024
    orig_name = (file.filename or "attachment")
    ext = orig_name.rsplit(".", 1)[-1].lower() if "." in orig_name else ""
    if ext not in _ALLOWED_EXTS:
        raise AppError(400, "ATTACHMENT_BAD_TYPE",
                       f"不支持的文件类型，允许：{', '.join(sorted(_ALLOWED_EXTS))}")
    sha = hashlib.sha256()
    size = 0
    head = b""
    while chunk := spool.read(_CHUNK_BYTES):
        if not head:
            head = chunk[:16]
        size += len(chunk)
        if size > limit:
            raise AppError(413, "ATTACHMENT_TOO_LARGE", f"附件超过 {_MAX_MB}MB 上限")
        sha.update(chunk)
    sniffed = _sniff_magic(head)
    if sniffed is None:
        raise AppError(400, "ATTACHMENT_BAD_TYPE", "文件内容与类型不符或已损坏")
    if ext in _ZIP_EXTS and sniffed != "zip":
        raise AppError(400, "ATTACHMENT_BAD_TYPE", "文件内容与扩展名不符")
    if ext in _OLE_EXTS and sniffed != "ole":
        raise AppError(400, "ATTACHMENT_BAD_TYPE", "文件内容与扩展名不符")
    if sniffed in {"png", "jpg", "gif", "pdf"} and ext not in {"jpeg", "webp"} \
            and sniffed != ext:
        raise AppError(400, "ATTACHMENT_BAD_TYPE", "文件内容与扩展名不符")
    return size, sha.hexdigest(), ext


def upload(
    db: Session,
    *,
    module: str,
    business_id: int | None,
    file: UploadFile,
    user_id: int,
) -> Attachment:
    """校验 + 落盘 + 落库，单事务提交。module/business 归属校验由 api 层先行。"""
    if module not in AttachmentModule:
        raise AppError(400, "ATTACHMENT_BAD_TYPE", "未知的附件模块")
    spool = tempfile.SpooledTemporaryFile(max_size=_SPOOL_MEM_BYTES)
    try:
        while chunk := file.file.read(_CHUNK_BYTES):
            spool.write(chunk)
        spool.seek(0)
        size, sha, ext = _check(file, spool)

        root = os.path.join(get_settings().upload_dir, "attachments")
        ym = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=8)).strftime("%Y%m")
        dir_path = os.path.join(root, ym)
        os.makedirs(dir_path, exist_ok=True)
        stored_path = os.path.join(dir_path, f"{sha}.{ext}")
        if not os.path.exists(stored_path):  # sha 寻址天然去重
            spool.seek(0)
            with open(stored_path, "wb") as dst:
                while chunk := spool.read(_CHUNK_BYTES):
                    dst.write(chunk)
    finally:
        spool.close()

    row = Attachment(
        module=module, business_id=business_id,
        orig_name=(file.filename or "attachment")[:256],
        stored_path=stored_path, sha256=sha, content_type=file.content_type,
        size_bytes=size, uploaded_by=user_id,
    )
    db.add(row)
    db.commit()
    return row


def owned_attachment(db: Session, attachment_id: int, user_id: int) -> Attachment:
    """归属校验：本人上传的，或本人订单下的凭证；否则 404 不泄露存在性。"""
    row = (
        db.query(Attachment)
        .outerjoin(Order, sa.and_(Order.id == Attachment.business_id,
                                  Attachment.module == AttachmentModule.ORDER_VOUCHER))
        .filter(
            Attachment.id == attachment_id, Attachment.deleted_at.is_(None),
            sa.or_(
                Attachment.uploaded_by == user_id,
                sa.and_(Attachment.module == AttachmentModule.ORDER_VOUCHER,
                        Order.user_id == user_id),
            ),
        )
        .first()
    )
    if row is None:
        raise AppError(404, "ATTACHMENT_NOT_FOUND", "附件不存在")
    return row


def get_for_admin(db: Session, attachment_id: int) -> Attachment:
    row = (
        db.query(Attachment)
        .filter(Attachment.id == attachment_id, Attachment.deleted_at.is_(None))
        .first()
    )
    if row is None:
        raise AppError(404, "ATTACHMENT_NOT_FOUND", "附件不存在")
    return row


def list_all(db: Session, *, module: str | None = None, business_id: int | None = None,
             limit: int = 20, offset: int = 0) -> tuple[list[Attachment], int]:
    q = db.query(Attachment).filter(Attachment.deleted_at.is_(None))
    if module:
        q = q.filter(Attachment.module == module)
    if business_id is not None:
        q = q.filter(Attachment.business_id == business_id)
    total = q.count()
    return q.order_by(Attachment.id.desc()).offset(offset).limit(min(limit, 100)).all(), total


def soft_delete(db: Session, row: Attachment) -> None:
    row.deleted_at = dt.datetime.now(dt.UTC)
    db.commit()


def hard_delete_expired(db: Session, cutoff: dt.datetime) -> int:
    """purge 生命周期任务调用：软删超期附件回收物理文件（引用计数，唯一硬删入口）。"""
    rows = (
        db.query(Attachment)
        .filter(Attachment.deleted_at.is_not(None), Attachment.deleted_at < cutoff)
        .all()
    )
    removed = 0
    for row in rows:
        still_used = (
            db.query(Attachment.id)
            .filter(Attachment.sha256 == row.sha256,
                    Attachment.id != row.id,
                    Attachment.deleted_at.is_(None))
            .first()
        )
        if still_used is None and os.path.exists(row.stored_path):
            try:
                os.unlink(row.stored_path)
            except OSError:
                pass
        db.delete(row)
        removed += 1
    db.commit()
    return removed
