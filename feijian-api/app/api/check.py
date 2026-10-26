from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.models import CheckItem, Report, User
from app.schemas.check import CheckItemOut, CheckItemsPage, ReportOut
from app.services import compare_svc, project_svc

router = APIRouter(tags=["check"])


@router.get("/projects/{pid}/check-items", response_model=CheckItemsPage)
def list_check_items(
    pid: int,
    category: str | None = None,
    page: int = 1,
    size: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = project_svc.get_owned(db, pid, user.id)
    q = db.query(CheckItem).filter(CheckItem.project_id == project.id)
    if category:
        q = q.filter(CheckItem.category == category)
    total = q.count()
    items = q.order_by(CheckItem.id.asc()).offset((max(page, 1) - 1) * size).limit(min(size, 100)).all()
    stats = dict(
        db.query(CheckItem.category, func.count(CheckItem.id))
        .filter(CheckItem.project_id == project.id)
        .group_by(CheckItem.category)
        .all()
    )
    return CheckItemsPage(
        items=[CheckItemOut.model_validate(i) for i in items],
        total=total,
        stats=stats,
    )


@router.post("/projects/{pid}/checklist-report", status_code=501)
def make_checklist_report(
    pid: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project_svc.get_owned(db, pid, user.id)
    # 业务端点：清单生成引擎（M1，见 02 §3-§4）未接入前明确 501，避免半成品语义
    raise AppError(501, "NOT_IMPLEMENTED", "清单生成引擎未接入（骨架版）——M1 实现")


@router.post("/projects/{pid}/compare", status_code=202)
def start_compare(
    pid: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = project_svc.get_owned(db, pid, user.id)
    cmp_, task_id = compare_svc.start_compare(db, user, project)
    return {"comparison_id": cmp_.id, "task_id": task_id}  # 02 §9.4 响应契约


@router.get("/projects/{pid}/comparison")
def latest_comparison(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_svc.get_owned(db, pid, user.id)
    cmp_ = compare_svc.latest(db, project)
    return {
        "id": cmp_.id, "status": cmp_.status, "stats": cmp_.stats,
        "created_at": cmp_.created_at.isoformat(),
        "finished_at": cmp_.finished_at.isoformat() if cmp_.finished_at else None,
    }


@router.get("/reports/{rid}", response_model=ReportOut)
def get_report(rid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import Project

    report = (
        db.query(Report)
        .join(Project, Report.project_id == Project.id)
        .filter(Report.id == rid, Project.user_id == user.id)
        .first()
    )
    if report is None:
        raise AppError(404, "REPORT_NOT_FOUND", "报告不存在")
    return ReportOut.model_validate(report)


@router.get("/reports/{rid}/export", status_code=501)
def export_report(
    rid: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models import Project

    report = (
        db.query(Report)
        .join(Project, Report.project_id == Project.id)
        .filter(Report.id == rid, Project.user_id == user.id)
        .first()
    )
    if report is None:
        raise AppError(404, "REPORT_NOT_FOUND", "报告不存在")
    # 业务端点：HTML 渲染（M07 renderer，见 02 §6.2）未接入前明确 501
    raise AppError(501, "NOT_IMPLEMENTED", "报告导出引擎未接入（骨架版）——M1 实现")
