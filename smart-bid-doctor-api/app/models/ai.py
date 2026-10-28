"""AI 治理域模型（05 §9）：模型注册与 Prompt 版本管理。

- AiModelConfig：模型注册表（用途映射/计价快照 元每百万 token/rpm 限流/开关）——
  M1 LLM Provider 接入时读取此处计价与开关，切换供应商=新增注册行（D1 抽象不变）；
- PromptTemplate：prompt 版本管理（name+version 唯一，同 purpose 仅一个 is_active）；
  模板切换必须先跑金标评测（make eval）锚定 eval_score（ai_prompt_switch 审计）。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PkMixin, TimestampMixin


class AiModelConfig(Base, PkMixin, TimestampMixin):
    """模型注册表（05 §9.3）：停用即拒绝新调用（进行中任务不受影响）。"""

    __tablename__ = "ai_model_config"

    model_code: Mapped[str] = mapped_column(String(32), unique=True)  # glm-4.6 | glm-4.5-flash
    provider: Mapped[str] = mapped_column(String(16))  # zhipu | ...
    purpose: Mapped[str] = mapped_column(String(24))  # heavy | light | embed
    input_price: Mapped[float] = mapped_column(Numeric(10, 4), default=0)  # 元/百万 token
    output_price: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    rpm_limit: Mapped[int | None] = mapped_column(Integer)  # 限流（NULL=不限）
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    remark: Mapped[str | None] = mapped_column(String(256))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class PromptTemplate(Base, PkMixin, TimestampMixin):
    """Prompt 版本（05 §9.3）：同 (purpose) 仅一个 active；eval_score 为评测回归锚点。"""

    __tablename__ = "prompt_templates"

    name: Mapped[str] = mapped_column(String(64))  # extract_v3 | judge_v2 ...
    purpose: Mapped[str] = mapped_column(String(24))  # extract | judge | summary | retry
    version: Mapped[int] = mapped_column(Integer)
    template: Mapped[str] = mapped_column(Text)  # 模板全文（占位符）
    variables: Mapped[dict | None] = mapped_column(JSONB)  # 模板变量说明
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    eval_score: Mapped[dict | None] = mapped_column(JSONB)  # 最近一次金标评测指标
    updated_by: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        Index("uq_prompt_version", "name", "version", unique=True),
        Index("idx_prompt_active", "purpose", postgresql_where=text("is_active = true")),
    )
