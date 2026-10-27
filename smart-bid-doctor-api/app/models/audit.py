"""审计日志（03 §2.12 audit_logs）：人为操作留痕，与业务事务解耦。

写入统一走 audit_svc.log（独立事务、失败不阻断主业务、自动附带 request_id）；
INET 强类型列写入前经 _safe_ip 校验（非法值归 NULL）；detail JSONB 存业务上下文，
`detail.request_id` ↔ 响应头 X-Request-ID ↔ tasks ↔ 结构化日志四链互查。
"""

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PkMixin, TimestampMixin


class AuditLog(Base, PkMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    action: Mapped[str] = mapped_column(String(48))  # login|upload|compare|order_grant|...
    target: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip: Mapped[str | None] = mapped_column(INET)

    __table_args__ = (
        Index("idx_audit_user", "user_id", "created_at"),
        Index("idx_audit_action", "action", "created_at"),
    )
