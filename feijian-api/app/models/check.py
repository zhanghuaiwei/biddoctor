from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PkMixin, TimestampMixin, UuidMixin


class CheckItem(Base, PkMixin, UuidMixin, TimestampMixin):
    __tablename__ = "check_items"

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE")
    )
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("documents.id"))
    code: Mapped[str] = mapped_column(String(16))  # STAR-007 / QUAL-003 / ...
    category: Mapped[str] = mapped_column(String(16))
    # qualification | compliance | star | price | format_seal
    requirement: Mapped[str] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text)
    ref_page: Mapped[int] = mapped_column(Integer)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    check_hint: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), default=1.00)

    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_check_items_code"),
        Index("idx_check_items_proj_cat", "project_id", "category"),
    )


class Comparison(Base, PkMixin, UuidMixin, TimestampMixin):
    __tablename__ = "comparisons"

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE")
    )
    tender_doc_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("documents.id"))
    bid_doc_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("documents.id"))
    order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # 03: 无 FK（nullable=免费/邀测）
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending | running | done | failed | need_review
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Finding(Base, PkMixin, TimestampMixin):
    __tablename__ = "findings"

    comparison_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("comparisons.id", ondelete="CASCADE")
    )
    check_item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("check_items.id"))
    verdict: Mapped[str] = mapped_column(String(12))  # satisfied|deviated|missing|uncertain
    level: Mapped[str] = mapped_column(String(8))  # red | yellow | green
    reason: Mapped[str] = mapped_column(Text)
    bid_ref_page: Mapped[int | None] = mapped_column(Integer)
    bid_quote: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2))
    rule_overridden: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("idx_findings_cmp", "comparison_id", "level"),
        Index("idx_findings_item", "check_item_id"),
    )


class Report(Base, PkMixin, UuidMixin, TimestampMixin):
    __tablename__ = "reports"

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(12))  # checklist | comparison
    comparison_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("comparisons.id"), nullable=True
    )
    report_data: Mapped[dict] = mapped_column(JSONB)
    html_path: Mapped[str | None] = mapped_column(String(512))

    __table_args__ = (Index("idx_reports_project", "project_id", "created_at"),)
