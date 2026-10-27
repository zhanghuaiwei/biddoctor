import io

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Document
from app.services import task_svc
from app.services.storage import LocalStorage


def _check_pdf(data: bytes) -> int:
    """PDF 魔数/加密/页数校验，返回页数（02 §2.2 接收校验）"""
    if not data.startswith(b"%PDF"):
        raise AppError(400, "PARSE_CORRUPT", "不是有效的 PDF 文件")
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise AppError(400, "PARSE_ENCRYPTED", "文件已加密，请上传解密后的 PDF")
        pages = len(reader.pages)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(400, "PARSE_CORRUPT", "PDF 无法解析，文件可能已损坏") from exc
    s = get_settings()
    if pages > s.max_pages:
        raise AppError(413, "FILE_TOO_MANY_PAGES", f"页数超过上限 {s.max_pages} 页，请拆分后上传")
    return pages


def upload(
    db: Session,
    storage: LocalStorage,
    *,
    project_id: int,
    role: str,
    file: UploadFile,
) -> tuple[Document, bool, int | None]:
    """校验 + 落盘 + 建解析任务，单事务提交。返回 (document, dup, task_id)。"""
    s = get_settings()
    data = file.file.read(s.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise AppError(413, "FILE_TOO_LARGE", f"文件超过 {s.max_upload_mb}MB 上限")
    pages = _check_pdf(data)
    sha, stored_path = storage.save(data)

    dup = (
        db.query(Document)
        .filter(Document.sha256 == sha, Document.deleted_at.is_(None))
        .first()
        is not None
    )
    doc = Document(
        project_id=project_id,
        role=role,
        orig_name=file.filename or "upload.pdf",
        stored_path=stored_path,
        sha256=sha,
        size_bytes=len(data),
        total_pages=pages,
        # 同 sha 文件视为已解析（TODO(M1): 业务接入后应复用解析结果而非跳过）
        parse_status="done" if dup else "pending",
        parse_warnings=[] if not dup else ["重复文件：复用已有解析结果（骨架版未复用）"],
        embedding_status="skipped" if dup else "pending",
    )
    db.add(doc)
    db.flush()
    task_id = None
    if not dup:
        task = task_svc.create(db, type_="parse", project_id=project_id, document_id=doc.id)
        task_id = task.id
    db.commit()
    return doc, dup, task_id


def owned_document(db: Session, document_id: int, user_id: int) -> Document:
    """归属校验：非本人项目下的文档一律 404（不泄露存在性）"""
    from app.models import Project

    doc = (
        db.query(Document)
        .join(Project, Document.project_id == Project.id)
        .filter(Document.id == document_id, Document.deleted_at.is_(None),
                Project.user_id == user_id, Project.deleted_at.is_(None))
        .first()
    )
    if doc is None:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "文件不存在")
    return doc


def list_by_project(db: Session, project_id: int) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.project_id == project_id, Document.deleted_at.is_(None))
        .order_by(Document.id.asc())
        .all()
    )
