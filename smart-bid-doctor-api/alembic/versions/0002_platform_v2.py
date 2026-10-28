"""平台化 v2.0 全量表（05 文档 §3/§20-40，26 张新表）+ 业务表平台扩展列

Revision ID: 0002
Create Date: 2026-10-28

幂等设计说明：0001 采用 Base.metadata.create_all 建表，models 元数据扩充后，
全新库执行 0001 时平台表/扩展列已一并建出；为兼容「已跑过 0001 的存量库」与
「全新库」两条路径，本迁移对所有建表/加列/加索引操作先探查再执行（检查到已
存在即跳过），保证两条路径升级结果一致。
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# 平台域/商业化域新增表（05 §20-40）
NEW_TABLES = [
    "sys_org", "sys_role", "sys_user_role", "sys_menu", "sys_role_menu",
    "sys_config", "sys_dict_type", "sys_dict_data", "sys_notice",
    "sys_job", "sys_job_log", "sys_login_log", "sys_oper_log",
    "sys_stats_daily", "sys_alert_log", "invite_codes",
    "attachments", "legal_documents", "user_agreements",
    "ai_model_config", "prompt_templates",
    "payments", "subscription_plans", "subscriptions",
    "rule_sets", "rule_items",
]

# 业务表平台扩展列（表, 列, Column 定义）
NEW_COLUMNS = [
    ("users", sa.Column("org_id", sa.BigInteger(), nullable=True)),
    ("llm_calls", sa.Column("model_id", sa.BigInteger(), nullable=True)),
    ("llm_calls", sa.Column("prompt_template_id", sa.BigInteger(), nullable=True)),
    ("check_items", sa.Column("law_basis", sa.Text(), nullable=True)),
    ("findings", sa.Column("feedback", sa.String(length=8), nullable=True)),
    ("findings", sa.Column("feedback_note", sa.Text(), nullable=True)),
    ("findings", sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True)),
    ("reports", sa.Column("disclaimer_ack", sa.Boolean(), nullable=False,
                          server_default=sa.false())),
]

# 存量表新增索引（表, 索引名, 列, where）
NEW_INDEXES = [
    ("users", "idx_users_org", ["org_id"], "deleted_at IS NULL"),
]


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def _has_column(insp, table: str, name: str) -> bool:
    return any(c["name"] == name for c in insp.get_columns(table))


def _has_index(insp, table: str, name: str) -> bool:
    return any(i["name"] == name for i in insp.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    from app.models import Base

    new_tables = [Base.metadata.tables[n] for n in NEW_TABLES if not _has_table(insp, n)]
    if new_tables:
        Base.metadata.create_all(bind, tables=new_tables)

    for table, col in NEW_COLUMNS:
        if _has_table(insp, table) and not _has_column(insp, table, col.name):
            op.add_column(table, col)

    for table, name, cols, where in NEW_INDEXES:
        if _has_table(insp, table) and not _has_index(insp, table, name):
            op.create_index(name, table, cols, postgresql_where=sa.text(where))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for table, name, cols, where in NEW_INDEXES:
        if _has_table(insp, table) and _has_index(insp, table, name):
            op.drop_index(name, table_name=table)

    for table, col in reversed(NEW_COLUMNS):
        if _has_table(insp, table) and _has_column(insp, table, col.name):
            op.drop_column(table, col.name)

    for name in reversed(NEW_TABLES):
        if _has_table(insp, name):
            op.drop_table(name)
