from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.enums import DocumentRole
from app.core.errors import ERROR_CODES, AppError
from app.models import User
from app.schemas.project import (
    DocumentListOut,
    DocumentOut,
    DocumentStatusOut,
    ProjectIn,
    ProjectOut,
    ProjectPage,
    UploadOut,
)
from app.services import (
    audit_svc,
    document_svc,
    project_svc,
    task_svc,
)
from app.services.storage import LocalStorage

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_svc.create(db, user.id, name=body.name, industry=body.industry)
    audit_svc.log(db, user.id, audit_svc.AuditAction.PROJECT_CREATED, target=str(project.id),
                  detail={"name": project.name, "industry": project.industry})
    return project


@router.get("", response_model=ProjectPage)
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
    audit_svc.log(db, user.id, audit_svc.AuditAction.PROJECT_DELETED, target=str(project.id),
                  detail={"name": project.name})


@router.post("/{pid}/documents", response_model=UploadOut, status_code=201)
def upload_document(
    pid: int,
    file: UploadFile = File(...),
    role: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if role not in (DocumentRole.TENDER, DocumentRole.BID):
        raise AppError(ERROR_CODES["BAD_ROLE"], "BAD_ROLE", "role 必须为 tender 或 bid")
    project = project_svc.get_owned(db, pid, user.id)
    storage = LocalStorage(get_settings().upload_dir)
    doc, dup, task_id = document_svc.upload(db, storage, project_id=project.id, role=role, file=file)
    audit_svc.log(db, user.id, audit_svc.AuditAction.UPLOAD, target=str(doc.id), detail={"role": role, "dup": dup})
    return UploadOut(document_id=doc.id, task_id=task_id, dup=dup)  # 02 §9.2 响应契约


@router.get("/documents/{did}/status", response_model=DocumentStatusOut)
def document_status(did: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = document_svc.owned_document(db, did, user.id)
    task = task_svc.latest_for_document(db, doc.id)
    return DocumentStatusOut(
        parse_status=doc.parse_status,
        progress=task_svc.display_progress(task, doc.parse_status),
        stage=task.stage if task else None,
        warnings=doc.parse_warnings or [],
        is_scanned_ratio=(
            float(doc.is_scanned_ratio) if doc.is_scanned_ratio is not None else None
        ),
        task_id=task.id if task else None,
    )


@router.get("/{pid}/documents", response_model=DocumentListOut)
def list_documents(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_svc.get_owned(db, pid, user.id)
    docs = document_svc.list_by_project(db, project.id)
    return DocumentListOut(items=[DocumentOut.model_validate(d) for d in docs])
