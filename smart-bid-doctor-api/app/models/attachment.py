"""附件与法务合规域模型（05 §7 / §8）。

- Attachment：通用附件（module + business_id 弱关联），documents（标书原件）保持独立
  不迁移；sha256 去重存储，物理文件随 purge 周期按引用计数回收；
- LegalDocument：用户协议/隐私政策/免责声明三类版本化管理（Markdown 全文入库）；
- UserAgreement：用户签署记录（PIPL「告知-同意」留痕，可追溯）。
"""

from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PkMixin, TimestampMixin, UuidMixin


class Attachment(Base, PkMixin, UuidMixin, TimestampMixin):
    """通用附件（05 §7）：module 白名单见 enums.AttachmentModule。"""

    __tablename__ = "attachments"

    module: Mapped[str] = mapped_column(String(32))  # order_voucher | appeal | import | profile
    business_id: Mapped[int | None] = mapped_column(BigInteger)  # 关联业务主键（弱关联无 FK）
    orig_name: Mapped[str] = mapped_column(String(256))
    stored_path: Mapped[str] = mapped_column(String(512))  # /data/attachments/<ym>/<sha256><ext>
    sha256: Mapped[str] = mapped_column(CHAR(64))
    content_type: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    uploaded_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_attachments_biz", "module", "business_id",
              postgresql_where=text("deleted_at IS NULL")),
        Index("idx_attachments_sha", "sha256"),
    )


class LegalDocument(Base, PkMixin, TimestampMixin):
    """法务文档版本（05 §8.1）：draft → effective（effective_at 生效）→ retired。"""

    __tablename__ = "legal_documents"

    doc_type: Mapped[str] = mapped_column(String(16))  # user_agreement | privacy_policy | disclaimer
    version: Mapped[str] = mapped_column(String(16))  # 如 v1.2
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)  # Markdown 全文
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="draft")

    __table_args__ = (Index("uq_legal_doc", "doc_type", "version", unique=True),)


class UserAgreement(Base, PkMixin, TimestampMixin):
    """用户签署记录：注册/登录首次勾选、新版本生效后再次确认均落一行。"""

    __tablename__ = "user_agreements"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    legal_doc_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("legal_documents.id"))
    ip: Mapped[str | None] = mapped_column(String(64))  # INET 语义，写入前 _safe_ip 校验
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (Index("idx_user_agreements_user", "user_id", "signed_at"),)
