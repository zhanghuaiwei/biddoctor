import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.enums import ProjectStatus
from app.core.errors import AppError
from app.models import Project, User
from app.services import quota_svc


def create(db: Session, user_id: int, *, name: str, industry: str) -> Project:
    # 行锁串行化并发创建：免费配额是计数型规则，check-then-act 无锁会被并发击穿超发
    db.execute(sa.select(User.id).where(User.id == user_id).with_for_update())
    if quota_svc.free_left(db, user_id) <= 0:
        raise AppError(402, "QUOTA_EXCEEDED", "本月免费项目额度已用完")
    p = Project(
        user_id=user_id,
        name=name,
        industry=industry,
        status=ProjectStatus.DRAFT,
        retain_until=dt.datetime.now(dt.UTC) + dt.timedelta(days=30),  # 03 §5 留存期
    )
    db.add(p)
    db.commit()
    return p


def get_owned(db: Session, project_id: int, user_id: int) -> Project:
    p = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user_id, Project.deleted_at.is_(None))
        .first()
    )
    if p is None:
        raise AppError(404, "PROJECT_NOT_FOUND", "项目不存在")
    return p


def list_owned(
    db: Session, user_id: int, *, status: str | None = None,
    limit: int = 20, offset: int = 0,
) -> tuple[list[Project], int]:
    q = db.query(Project).filter(Project.user_id == user_id, Project.deleted_at.is_(None))
    if status:  # 02 §9.2：GET /projects?status=
        q = q.filter(Project.status == status)
    total = q.count()
    return (
        q.order_by(Project.updated_at.desc()).offset(offset).limit(min(limit, 100)).all(),
        total,
    )


def soft_delete(db: Session, project: Project) -> None:
    project.deleted_at = dt.datetime.now(dt.UTC)
    project.status = ProjectStatus.ARCHIVED
    db.commit()
