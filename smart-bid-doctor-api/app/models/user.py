"""用户与验证码（03 §2.2 users / verification_codes）。

- User：邮箱为唯一登录标识（全串 lower 归一，注册/登录同口径）；软删用户登录查询
  过滤 `deleted_at IS NULL`（部分索引同步过滤）；phone 为 P2 短信通道预留列；
- VerificationCode：一次性凭据——消费必须走原子 UPDATE + rowcount 判定
  （auth_svc.login），禁 check-then-act。
"""

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
    # [平台扩展列 05 §2] 所属机构：NULL=平台直营个人用户；细粒度权限走 sys_user_role
    org_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_org.id"))
    invited_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_users_email", "email", postgresql_where=text("deleted_at IS NULL")),
        Index("idx_users_org", "org_id", postgresql_where=text("deleted_at IS NULL")),
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
