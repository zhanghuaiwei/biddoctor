"""检查清单 / 报告查询业务（02 §9.3、§9.4）。api 层只做参数接收与响应组装。"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import CheckCategory
from app.core.errors import AppError
from app.models import CheckItem, Project, Report


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
