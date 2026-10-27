"""初始建表（03-数据库设计 v1.0 全部 14 张表 + pgvector/pg_trgm 扩展 + 索引）

Revision ID: 0001
Revises:
Create Date: 2026-10-25

说明：初始迁移直接以 app.models 的 Base.metadata 建表（DDL 单一来源在 models，
与 03-数据库设计一一对应）。后续 schema 变更统一走
`alembic revision --autogenerate -m "..."` 产出显式迁移，不再用 create_all。
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    from app.models import Base

    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    from app.models import Base

    Base.metadata.drop_all(op.get_bind())
