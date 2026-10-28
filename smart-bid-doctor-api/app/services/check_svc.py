"""检查清单 / 报告查询业务（02 §9.3、§9.4）。api 层只做参数接收与响应组装。"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import CheckCategory
from app.core.errors import AppError
from app.models import CheckItem, Comparison, Project, Report


def list_check_items(
    db: Session, project: Project, category: str | None, *, limit: int = 20, offset: int = 0
) -> tuple[list[CheckItem], int, dict[str, int]]:
    """分页清单（分页契约全站统一 limit/offset，见 02 §9 约定）+ 分类统计。"""
    q = db.query(CheckItem).filter(CheckItem.project_id == project.id)
    if category:
        q = q.filter(CheckItem.category == category)
    total = q.count()
    items = q.order_by(CheckItem.id.asc()).offset(offset).limit(limit).all()
    stats = dict(
        db.query(CheckItem.category, func.count(CheckItem.id))
        .filter(CheckItem.project_id == project.id)
        .group_by(CheckItem.category)
        .all()
    )
    return items, total, stats


def get_report_owned(db: Session, rid: int, user_id: int) -> Report | None:
    """报告归属校验： join 项目并过滤项目软删（软删项目的报告一并不可见）。"""
    return (
        db.query(Report)
        .join(Project, Report.project_id == Project.id)
        .filter(
            Report.id == rid,
            Project.user_id == user_id,
            Project.deleted_at.is_(None),
        )
        .first()
    )


def owned_report(db: Session, rid: int, user_id: int) -> Report:
    """归属校验 + 404 语义收敛：非本人/软删项目的报告一律 404（不泄露存在性）。"""
    report = get_report_owned(db, rid, user_id)
    if report is None:
        raise AppError(404, "REPORT_NOT_FOUND", "报告不存在")
    return report


def latest_report(db: Session, project: Project) -> Report | None:
    return (
        db.query(Report)
        .filter(Report.project_id == project.id)
        .order_by(Report.id.desc())
        .first()
    )


# 供 schema/文档引用的分类取值域（02 §3.1 五类条款）
CHECK_CATEGORIES: tuple[str, ...] = tuple(c.value for c in CheckCategory)


# ============================================================================
# 报告生成闭环（M1/D 实装：快照 → 渲染 → 落库 → 阅后即焚），handler 调用。
# ============================================================================


def tender_document(db: Session, project: Project):
    from app.models import Document

    return (
        db.query(Document)
        .filter(
            Document.project_id == project.id,
            Document.role == "tender",
            Document.deleted_at.is_(None),
        )
        .first()
    )


def create_checklist_task(db: Session, project: Project):
    """生成清单报告任务（api 层前置校验后调用）：与业务同事务，只 flush 不 commit。"""
    from app.services import task_svc

    return task_svc.create(db, type_="checklist", project_id=project.id)


def generate_checklist_report(db: Session, project: Project) -> Report:
    """清单报告闭环：快照 → 渲染 → 落盘 → reports 落库 → 阅后即焚软删原件。

    items 为空（抽取引擎未接入/无条款）仍生成完整报告结构（框架 + 免责声明 + 提示），
    保证「上传→解析→清单报告」业务链路端到端可用（M1 抽取接入后自动出数）。
    """
    import datetime as dt

    from app.engine import report as report_engine
    from app.models import Document

    doc = tender_document(db, project)
    if doc is None:
        raise AppError(400, "DOC_MISSING", "项目缺少招标文件，无法生成清单")
    items = (
        db.query(CheckItem)
        .filter(CheckItem.project_id == project.id)
        .order_by(CheckItem.id.asc())
        .all()
    )
    data = report_engine.build_checklist_data(project, doc, items)
    html = report_engine.render("checklist", data, model="pending-llm")
    html_path = report_engine.save_html(html)

    rep = Report(project_id=project.id, kind="checklist", report_data=data, html_path=html_path)
    db.add(rep)
    if project.status not in ("archived", "comparing"):
        project.status = "report_ready"
    # 阅后即焚（03 §5 / D3）：报告落库同事务软删原件——物理文件与 doc_blocks 随 purge 回收
    docs = (
        db.query(Document)
        .filter(Document.project_id == project.id, Document.deleted_at.is_(None))
        .all()
    )
    for d in docs:
        d.deleted_at = dt.datetime.now(dt.UTC)
    db.commit()
    return rep


def generate_comparison_report(db: Session, comparison) -> Report:
    """对照报告闭环（M2 判定接入后由 compare handler 调用；本封装先行就绪）。"""
    from app.engine import report as report_engine

    project = comparison_project(db, comparison)
    items = (
        db.query(CheckItem).filter(CheckItem.project_id == comparison.project_id).all()
    )
    findings = comparison_findings(db, comparison)
    data = report_engine.build_comparison_data(project, comparison, items, findings)
    html = report_engine.render("comparison", data)
    html_path = report_engine.save_html(html)
    rep = Report(
        project_id=comparison.project_id, kind="comparison",
        comparison_id=comparison.id, report_data=data, html_path=html_path,
    )
    db.add(rep)
    db.commit()
    return rep


def comparison_project(db: Session, comparison) -> "Project":
    project = db.get(Project, comparison.project_id)
    if project is None:
        raise AppError(404, "PROJECT_NOT_FOUND", "项目不存在")
    return project


def comparison_findings(db: Session, comparison) -> list:
    from app.models import Finding

    return (
        db.query(Finding)
        .filter(Finding.comparison_id == comparison.id)
        .order_by(Finding.id.asc())
        .all()
    )


def ack_disclaimer(db: Session, report: Report) -> Report:
    """免责声明确认（查看/导出前勾选，reports.disclaimer_ack P2 扩展列）。"""
    report.disclaimer_ack = True
    db.commit()
    return report


def set_finding_feedback(
    db: Session, finding_id: int, user_id: int, feedback: str, note: str | None
) -> None:
    """误报/认可标记（P2 质量回流，05 §6.2 finding_feedback_disagree_rate 数据源）。

    归属校验：finding → comparison → project.user_id；非本人 404。
    """
    import datetime as dt

    from app.models import Finding

    row = (
        db.query(Finding)
        .join(Comparison, Finding.comparison_id == Comparison.id)
        .join(Project, Comparison.project_id == Project.id)
        .filter(
            Finding.id == finding_id,
            Project.user_id == user_id,
            Project.deleted_at.is_(None),
        )
        .first()
    )
    if row is None:
        raise AppError(404, "FINDING_NOT_FOUND", "判定记录不存在")
    row.feedback = feedback
    row.feedback_note = note
    row.feedback_at = dt.datetime.now(dt.UTC)
    db.commit()


def list_reports(db: Session, project: Project, *, limit: int = 20, offset: int = 0):
    q = db.query(Report).filter(Report.project_id == project.id)
    total = q.count()
    return q.order_by(Report.id.desc()).offset(offset).limit(min(limit, 100)).all(), total
