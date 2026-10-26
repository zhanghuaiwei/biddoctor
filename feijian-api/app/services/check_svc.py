"""检查清单 / 报告查询业务（02 §9.4）。api 层只做参数接收与响应组装。"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import CheckItem, Project, Report


def list_check_items(
    db: Session, project: Project, category: str | None, page: int, size: int
) -> tuple[list[CheckItem], int, dict[str, int]]:
    q = db.query(CheckItem).filter(CheckItem.project_id == project.id)
    if category:
        q = q.filter(CheckItem.category == category)
    total = q.count()
    items = q.order_by(CheckItem.id.asc()).offset((page - 1) * size).limit(size).all()
    stats = dict(
        db.query(CheckItem.category, func.count(CheckItem.id))
        .filter(CheckItem.project_id == project.id)
        .group_by(CheckItem.category)
        .all()
    )
    return items, total, stats


def get_report_owned(db: Session, rid: int, user_id: int) -> Report | None:
    return (
        db.query(Report)
        .join(Project, Report.project_id == Project.id)
        .filter(Report.id == rid, Project.user_id == user_id)
        .first()
    )


def latest_report(db: Session, project: Project) -> Report | None:
    return (
        db.query(Report)
        .filter(Report.project_id == project.id)
        .order_by(Report.id.desc())
        .first()
    )
