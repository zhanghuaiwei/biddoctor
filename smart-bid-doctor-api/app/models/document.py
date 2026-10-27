"""文档与解析块（03 §2.4 documents / doc_blocks）。

- Document：原件元数据 + 解析/向量化状态机；sha256 内容寻址去重（同内容复用存储，
  purge 时按引用计数决定是否删物理文件）；原件留存策略见 purge（03 §5）；
- DocBlock：解析产物（页码/坐标/段落表格分类），M1 解析引擎写入；embedding 列 +
  HNSW 向量索引 + pg_trgm 文本索引，为 M2 对照的混合检索预置（02 §5）。
"""

from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CHAR,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import EMBED_DIM, Base, PkMixin, TimestampMixin, UuidMixin


class Document(Base, PkMixin, UuidMixin, TimestampMixin):
    __tablename__ = "documents"

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(8))  # tender | bid
    orig_name: Mapped[str] = mapped_column(String(256))
    stored_path: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(CHAR(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    total_pages: Mapped[int | None] = mapped_column(Integer)
    is_scanned_ratio: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    parse_status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending | running | done | failed | need_review
    parse_warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)
    embedding_status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending | done | skipped | failed
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "idx_documents_project",
            "project_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("idx_documents_sha", "sha256"),
    )


class DocBlock(Base, PkMixin, TimestampMixin):
    __tablename__ = "doc_blocks"

    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE")
    )
    page: Mapped[int] = mapped_column(Integer)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(8))  # heading | text | table
    text: Mapped[str] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(String(256))
    embedding = mapped_column(Vector(EMBED_DIM), nullable=True)

    __table_args__ = (
        Index("idx_blocks_doc", "document_id", "page", "seq"),
        Index(
            "idx_blocks_vec",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "idx_blocks_text_trgm",
            "text",
            postgresql_using="gin",
            postgresql_ops={"text": "gin_trgm_ops"},
        ),
    )
