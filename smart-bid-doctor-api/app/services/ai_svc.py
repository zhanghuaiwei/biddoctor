"""AI 治理（ai_model_config / prompt_templates，05 §9）：模型注册与 Prompt 版本管理。

- 模型注册表：M1 LLM Provider 接入时读取计价与开关；停用即拒绝新调用；
- Prompt 版本：同 purpose 仅一个 is_active；激活必须携带 eval_score
  （模板变更先跑金标评测——prompt 漂移即评测可追溯，05 §9.3）。
管理动作审计（ai_model_update / ai_prompt_publish / ai_prompt_switch）由 api 层写。
"""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import AiModelConfig, PromptTemplate

# ── 模型注册 ─────────────────────────────────────────────────────────────────


def list_models(db: Session) -> list[AiModelConfig]:
    return db.query(AiModelConfig).order_by(AiModelConfig.id.asc()).all()


def create_model(db: Session, **fields) -> AiModelConfig:
    dup = db.query(AiModelConfig.id).filter(
        AiModelConfig.model_code == fields["model_code"]).first()
    if dup:
        raise AppError(409, "AI_MODEL_CONFLICT", "该模型编码已注册")
    row = AiModelConfig(**fields)
    db.add(row)
    db.commit()
    return row


def update_model(db: Session, model_id: int, **fields) -> AiModelConfig:
    row = db.get(AiModelConfig, model_id)
    if row is None:
        raise AppError(404, "AI_MODEL_NOT_FOUND", "模型不存在")
    for k, v in fields.items():
        if v is not None:
            setattr(row, k, v)
    row.updated_at = dt.datetime.now(dt.UTC)
    db.commit()
    return row


def get_enabled(db: Session, model_code: str) -> AiModelConfig | None:
    """llm provider 接入点：停用即拒绝新调用（返回 None）。"""
    return (
        db.query(AiModelConfig)
        .filter(AiModelConfig.model_code == model_code,
                AiModelConfig.enabled.is_(True))
        .first()
    )


# ── Prompt 版本 ──────────────────────────────────────────────────────────────


def list_prompts(db: Session, *, purpose: str | None = None) -> list[PromptTemplate]:
    q = db.query(PromptTemplate)
    if purpose:
        q = q.filter(PromptTemplate.purpose == purpose)
    return q.order_by(PromptTemplate.purpose.asc(),
                      PromptTemplate.version.desc()).all()


def create_prompt(db: Session, **fields) -> PromptTemplate:
    dup = db.query(PromptTemplate.id).filter(
        PromptTemplate.name == fields["name"],
        PromptTemplate.version == fields["version"]).first()
    if dup:
        raise AppError(409, "PROMPT_STATE", "同名同版本已存在")
    row = PromptTemplate(is_active=False, **fields)
    db.add(row)
    db.commit()
    return row


def activate_prompt(db: Session, prompt_id: int, admin_id: int) -> PromptTemplate:
    """切换 active：必须已有 eval_score（金标评测锚定），同 purpose 旧 active 退位。"""
    row = db.get(PromptTemplate, prompt_id)
    if row is None:
        raise AppError(404, "PROMPT_NOT_FOUND", "Prompt 版本不存在")
    if not row.eval_score:
        raise AppError(409, "PROMPT_STATE", "缺少金标评测结果（eval_score），先跑 make eval")
    db.execute(
        sa.update(PromptTemplate)
        .where(PromptTemplate.purpose == row.purpose, PromptTemplate.is_active.is_(True))
        .values(is_active=False)
    )
    row.is_active = True
    row.updated_by = admin_id
    db.commit()
    return row


def active_prompt(db: Session, purpose: str) -> PromptTemplate | None:
    return (
        db.query(PromptTemplate)
        .filter(PromptTemplate.purpose == purpose, PromptTemplate.is_active.is_(True))
        .first()
    )
