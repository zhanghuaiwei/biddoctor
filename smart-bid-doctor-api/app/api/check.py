"""检查清单 / 对照 / 报告接口（02 §9.3–§9.4）。

已完成：清单分页查询（五类筛选 + 分类统计）、双文件对照发起（202）、对照结果查询、
报告详情/列表/导出（FileResponse，浏览器打印即 PDF）、清单报告生成（202 建任务，
worker 渲染闭环 + 阅后即焚）、免责声明确认、判定质量回流（P2 feedback）。
对照判定引擎（M2，LLM）未接入前 compare 走 need_review 桩——其报告封装已就绪。
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.models import User
from app.schemas.check import (
    CheckItemOut,
    CheckItemsPage,
    ChecklistStartedOut,
    CompareStartedOut,
    ComparisonOut,
    FeedbackIn,
    FeedbackOut,
    ReportOut,
    ReportPage,
)
from app.services import audit_svc, check_svc, compare_svc, project_svc

router = APIRouter(tags=["check"])

A = audit_svc.AuditAction


@router.get("/projects/{pid}/check-items", response_model=CheckItemsPage)
def list_check_items(
    pid: int,
    category: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = project_svc.get_owned(db, pid, user.id)
    items, total, stats = check_svc.list_check_items(
        db, project, category, limit=limit, offset=offset
    )
    return CheckItemsPage(
        items=[CheckItemOut.model_validate(i) for i in items],
        total=total,
        stats=stats,
    )


@router.post("/projects/{pid}/checklist-report", status_code=202,
             response_model=ChecklistStartedOut)
def make_checklist_report(
    pid: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """生成清单报告：前置校验（双文件/解析就绪 400 先于任务入队）→ 202 建 checklist 任务。

    前端轮询任务终态后拉取报告（GET /projects/{pid}/reports）。
    """
    project = project_svc.get_owned(db, pid, user.id)
    doc = check_svc.tender_document(db, project)
    if doc is None:
        raise AppError(400, "DOC_MISSING", "请先上传招标文件")
    if doc.parse_status not in ("done", "need_review"):
        raise AppError(400, "DOC_NOT_READY", "招标文件尚未解析完成，请稍后再试")
    task = check_svc.create_checklist_task(db, project)
    db.commit()
    return ChecklistStartedOut(task_id=task.id)


@router.post("/projects/{pid}/compare", status_code=202, response_model=CompareStartedOut)
def start_compare(
    pid: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = project_svc.get_owned(db, pid, user.id)
    cmp_, task_id = compare_svc.start_compare(db, user, project)
    audit_svc.log(
        db, user.id, A.COMPARE_STARTED, target=str(cmp_.id),
        detail={"project_id": project.id, "task_id": task_id},
    )
    return CompareStartedOut(comparison_id=cmp_.id, task_id=task_id)  # 02 §9.4


@router.get("/projects/{pid}/comparison", response_model=ComparisonOut)
def latest_comparison(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_svc.get_owned(db, pid, user.id)
    return compare_svc.latest(db, project)


@router.get("/projects/{pid}/reports", response_model=ReportPage)
def list_reports(
    pid: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = project_svc.get_owned(db, pid, user.id)
    rows, total = check_svc.list_reports(db, project, limit=limit, offset=offset)
    return ReportPage(items=[ReportOut.model_validate(r) for r in rows], total=total)


@router.get("/reports/{rid}", response_model=ReportOut)
def get_report(rid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ReportOut.model_validate(check_svc.owned_report(db, rid, user.id))


@router.post("/reports/{rid}/ack", response_model=ReportOut)
def ack_report(
    rid: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """免责声明确认（disclaimer_ack，05 §8.1 / 03 v1.2 §5）。"""
    report = check_svc.owned_report(db, rid, user.id)
    check_svc.ack_disclaimer(db, report)
    audit_svc.log(db, user.id, A.REPORT_ACK, target=f"report:{rid}")
    return ReportOut.model_validate(report)


@router.get("/reports/{rid}/export")
def export_report(
    rid: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出 HTML（FileResponse，浏览器打印即 PDF）；产物清理后回 410。"""
    report = check_svc.owned_report(db, rid, user.id)
    if not report.html_path or not os_path_exists(report.html_path):
        raise AppError(410, "REPORT_FILE_GONE", "报告文件已按留存策略清理")
    audit_svc.log(db, user.id, A.REPORT_EXPORTED, target=f"report:{rid}",
                  detail={"kind": report.kind})
    return FileResponse(
        report.html_path,
        media_type="text/html; charset=utf-8",
        filename=f"report-{report.id}.html",
    )


@router.post("/findings/{fid}/feedback", response_model=FeedbackOut)
def finding_feedback(
    fid: int,
    body: FeedbackIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """判定质量回流（P2，05 §6.2）：agree 认可 / disagree 误报标记 + 备注。"""
    if body.feedback not in ("agree", "disagree"):
        raise AppError(422, "VALIDATION_ERROR", "feedback 取值限 agree | disagree")
    check_svc.set_finding_feedback(db, fid, user.id, body.feedback, body.note)
    row = db_finding(db, fid)
    return FeedbackOut.model_validate(row)


def os_path_exists(path: str) -> bool:
    import os
    return os.path.exists(path)


def db_finding(db: Session, fid: int):
    from app.models import Finding

    return db.get(Finding, fid)
