from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PkMixin, TimestampMixin, UuidMixin


class User(Base, PkMixin, UuidMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True)  # 主登录标识（01·D8）
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)  # 二通道预留
    nickname: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16), default="user")  # user | admin
    status: Mapped[str] = mapped_column(String(16), default="active")
    invited_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_users_email", "email", postgresql_where=text("deleted_at IS NULL")),
    )


class VerificationCode(Base, PkMixin, TimestampMixin):
    __tablename__ = "verification_codes"

    channel: Mapped[str] = mapped_column(String(8))  # email | sms
    target: Mapped[str] = mapped_column(String(320))
    code: Mapped[str] = mapped_column(String(6))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_vcodes_target", "channel", "target", "created_at"),
    )
