from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.models import Document, Task, User
from app.schemas.project import (
    DocumentListOut,
    DocumentOut,
    DocumentStatusOut,
    ProjectIn,
    ProjectOut,
    ProjectPage,
    UploadOut,
)
from app.services import audit_svc, document_svc, project_svc
from app.services.storage import LocalStorage

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_svc.create(db, user.id, name=body.name, industry=body.industry)
    audit_svc.log(db, user.id, "project_created", target=str(project.id),
                  detail={"name": project.name, "industry": project.industry})
    return project


@router.get("")
def list_projects(
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    items, total = project_svc.list_owned(
        db, user.id, status=status, limit=limit, offset=offset
    )
    return ProjectPage(
        items=[ProjectOut.model_validate(p) for p in items], total=total
    )


@router.get("/{pid}", response_model=ProjectOut)
def get_project(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return project_svc.get_owned(db, pid, user.id)


@router.delete("/{pid}", status_code=204)
def delete_project(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_svc.get_owned(db, pid, user.id)
    project_svc.soft_delete(db, project)
    audit_svc.log(db, user.id, "project_deleted", target=str(project.id),
                  detail={"name": project.name})


@router.post("/{pid}/documents", status_code=201)
def upload_document(
    pid: int,
    file: UploadFile = File(...),
    role: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if role not in ("tender", "bid"):
        raise AppError(400, "BAD_ROLE", "role 必须为 tender 或 bid")
    project = project_svc.get_owned(db, pid, user.id)
    storage = LocalStorage(get_settings().upload_dir)
    doc, dup, task_id = document_svc.upload(db, storage, project_id=project.id, role=role, file=file)
    audit_svc.log(db, user.id, "upload", target=str(doc.id), detail={"role": role, "dup": dup})
    return UploadOut(document_id=doc.id, task_id=task_id, dup=dup)  # 02 §9.2 响应契约


@router.get("/documents/{did}/status", response_model=DocumentStatusOut)
def document_status(did: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = document_svc.owned_document(db, did, user.id)
    task = (
        db.query(Task)
        .filter(Task.document_id == doc.id, Task.type == "parse")
        .order_by(Task.id.desc())
        .first()
    )
    return DocumentStatusOut(
        parse_status=doc.parse_status,
        progress=task.progress if task else (100 if doc.parse_status == "done" else 0),
        stage=task.stage if task else None,
        warnings=doc.parse_warnings or [],
        is_scanned_ratio=float(doc.is_scanned_ratio) if doc.is_scanned_ratio is not None else None,
        task_id=task.id if task else None,
    )


@router.get("/{pid}/documents", response_model=DocumentListOut)
def list_documents(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_svc.get_owned(db, pid, user.id)
    docs = (
        db.query(Document)
        .filter(Document.project_id == project.id, Document.deleted_at.is_(None))
        .order_by(Document.id.asc())
        .all()
    )
    return DocumentListOut(items=[DocumentOut.model_validate(d) for d in docs])
