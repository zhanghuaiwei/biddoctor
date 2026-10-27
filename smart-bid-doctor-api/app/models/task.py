from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PkMixin, TimestampMixin


class Task(Base, PkMixin, TimestampMixin):
    __tablename__ = "tasks"

    project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    document_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    comparison_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("comparisons.id", ondelete="CASCADE"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(12))  # parse|extract|embed|checklist|compare
    status: Mapped[str] = mapped_column(String(12), default="pending")
    # pending|running|succeeded|failed|need_review|cancelled
    stage: Mapped[str | None] = mapped_column(String(32))
    progress: Mapped[int] = mapped_column(SmallInteger, default=0)
    attempt: Mapped[int] = mapped_column(SmallInteger, default=0)
    error_code: Mapped[str | None] = mapped_column(String(32))
    error_msg: Mapped[str | None] = mapped_column(Text)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "idx_tasks_claim",
            "status",
            "run_after",
            postgresql_where=text("status IN ('pending')"),
        ),
        Index("idx_tasks_doc", "document_id", "type"),
    )


class LlmCall(Base, PkMixin, TimestampMixin):
    __tablename__ = "llm_calls"

    task_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    purpose: Mapped[str] = mapped_column(String(24))  # extract|judge|summary|retry|embed
    model: Mapped[str] = mapped_column(String(32))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_cny: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0"))
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("idx_llm_calls_proj", "project_id", "created_at"),
        Index("idx_llm_calls_day", "created_at"),
    )
