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
