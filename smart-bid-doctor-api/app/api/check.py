"""检查清单 / 对照 / 报告接口（02 §9.3–§9.4）。

已完成：清单分页查询（五类筛选 + 分类统计）、双文件对照发起（202 + comparison/task id）、
对照结果查询、报告详情查询。
未接入（M1，显式 501 见 TODO）：清单报告生成、报告导出——业务引擎就绪前明确返回
NOT_IMPLEMENTED，避免半成品语义；两个端点已保留归属校验，状态语义与 200 时刻一致。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import ERROR_CODES, AppError
from app.models import User
from app.schemas.check import (
    CheckItemOut,
    CheckItemsPage,
    CompareStartedOut,
    ComparisonOut,
    ReportOut,
)
from app.services import audit_svc, check_svc, compare_svc, project_svc

router = APIRouter(tags=["check"])


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


@router.post("/projects/{pid}/checklist-report", status_code=501)
def make_checklist_report(
    pid: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project_svc.get_owned(db, pid, user.id)
    # TODO(M1/D2) 接入后流程：校验解析就绪（400 前置）→ 建 checklist 任务（202 返回
    #   task_id）→ worker checklist handler 调 engine.report 生成报告（渲染方案见
    #   app/engine/report/__init__.py TODO 块）。前端轮询任务终态后拉取报告。
    # 业务端点：清单生成引擎（M1，见 02 §3-§4）未接入前明确 501，避免半成品语义
    raise AppError(ERROR_CODES["NOT_IMPLEMENTED"], "NOT_IMPLEMENTED", "清单生成引擎未接入（骨架版）——M1 实现")


@router.post("/projects/{pid}/compare", status_code=202, response_model=CompareStartedOut)
def start_compare(
    pid: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = project_svc.get_owned(db, pid, user.id)
    cmp_, task_id = compare_svc.start_compare(db, user, project)
    audit_svc.log(
        db, user.id, audit_svc.AuditAction.COMPARE_STARTED, target=str(cmp_.id),
        detail={"project_id": project.id, "task_id": task_id},
    )
    return CompareStartedOut(comparison_id=cmp_.id, task_id=task_id)  # 02 §9.4


@router.get("/projects/{pid}/comparison", response_model=ComparisonOut)
def latest_comparison(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_svc.get_owned(db, pid, user.id)
    return compare_svc.latest(db, project)


@router.get("/reports/{rid}", response_model=ReportOut)
def get_report(rid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ReportOut.model_validate(check_svc.owned_report(db, rid, user.id))


@router.get("/reports/{rid}/export", status_code=501)
def export_report(
    rid: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_svc.owned_report(db, rid, user.id)  # 归属校验先行，语义与 200 时刻一致
    # TODO(M1/D2) 接入后：FileResponse(report.html_path, media_type="text/html")——
    #   渲染在 worker 侧完成，本端点只做归属校验 + 文件下发；缺失文件（磁盘清理后）
    #   回 410 语义错误码（新增需登记 ERROR_CODES）。
    # 业务端点：HTML 渲染（M06 renderer，见 02 §6.2）未接入前明确 501
    raise AppError(ERROR_CODES["NOT_IMPLEMENTED"], "NOT_IMPLEMENTED", "报告导出引擎未接入（骨架版）——M1 实现")
