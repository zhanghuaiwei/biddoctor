"""检查项目（03 §2.3 projects）。

status 状态机（02 §8）：draft → tender_parsing → checklist_ready → comparing →
report_ready（archived 由软删置位）；免费配额计数含软删项目（软删不释放当月名额，
quota_svc.free_left），retain_until 驱动 purge 生命周期任务（03 §5）。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PkMixin, TimestampMixin, UuidMixin


class Project(Base, PkMixin, UuidMixin, TimestampMixin):
    __tablename__ = "projects"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(128))
    industry: Mapped[str] = mapped_column(String(32), default="general")  # general | medical
    status: Mapped[str] = mapped_column(String(24), default="draft")
    # draft | tender_parsing | checklist_ready | comparing | report_ready | archived
    retain_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "idx_projects_user",
            "user_id",
            "updated_at",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
