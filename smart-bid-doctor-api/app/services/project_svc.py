"""项目业务（02 §9.2）：创建（含免费配额扣减）/ 查询 / 软删。

事务边界：本模块拥有自己的 commit；配额计数型规则走用户行锁（create 内
WITH FOR UPDATE 串行化并发创建），软删只置 deleted_at + status=archived，
不物理删除（硬删仅 purge 生命周期任务）。
"""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.enums import ProjectStatus
from app.core.errors import AppError
from app.models import Project, User
from app.services import quota_svc


def create(db: Session, user_id: int, *, name: str, industry: str) -> Project:
    """创建项目：先锁用户行再查免费配额（行锁串行化，防并发超发），402 引导付费。

    锁顺序说明：锁用户行 → 查计数 → 插入项目，单事务 commit；retain_until
    即原件留存截止（30 天，03 §5），到期由 purge 任务软删文档并删无引用文件。
    """
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
    """归属校验：非本人或软删项目一律 404（不泄露存在性，越权防护基线）。"""
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
    """分页查询（全站统一 limit/offset，上限 100）；status 过滤取值域见 ProjectStatus。"""
    q = db.query(Project).filter(Project.user_id == user_id, Project.deleted_at.is_(None))
    if status:  # 02 §9.2：GET /projects?status=
        q = q.filter(Project.status == status)
    total = q.count()
    return (
        q.order_by(Project.updated_at.desc()).offset(offset).limit(min(limit, 100)).all(),
        total,
    )


def soft_delete(db: Session, project: Project) -> None:
    """软删：置 deleted_at 并归档状态；当月免费名额不释放（quota_svc.free_left 注释）。"""
    project.deleted_at = dt.datetime.now(dt.UTC)
    project.status = ProjectStatus.ARCHIVED
    db.commit()
