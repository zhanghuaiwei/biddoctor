"""模型公共基类与 Mixin（03 §2.1 公共约定）。

- PkMixin：BigInteger Identity 主键（分布式不依赖，迁移只加不删的前提下够用）；
- UuidMixin：对外暴露的非递增标识（防 ID 遍历探测），gen_random_uuid() 服务端生成；
- TimestampMixin：created_at 全部 TIMESTAMPTZ + server_default（时间范式见 AGENTS.md）；
- EMBED_DIM：pgvector 维度常量，与迁移、03 数据库设计三处同步。
"""

import uuid as _uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBED_DIM = 1024  # 智谱 embedding-3 dimensions=1024；与 03 数据库设计一致，改这里必须同步迁移


class Base(DeclarativeBase):
    pass


class PkMixin:
    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )


class UuidMixin:
    # 列名 uuid 会遮蔽 uuid 模块，类型引用必须走 _uuid
    uuid: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, server_default=text("gen_random_uuid()")
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
