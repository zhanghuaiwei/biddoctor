"""ORM 模型汇总出口（DDL 唯一来源，对应 03-数据库设计 §2 + 05 平台域全部表）。

改任何模型 → `alembic revision --autogenerate` 生成迁移（迁移只加不删）；
业务代码统一 `from app.models import X` 引用，不深入子模块导入。
"""

from app.models.ai import AiModelConfig, PromptTemplate
from app.models.attachment import Attachment, LegalDocument, UserAgreement
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.billing import Order, QuotaAccount
from app.models.check import CheckItem, Comparison, Finding, Report
from app.models.commerce import Payment, RuleItem, RuleSet, Subscription, SubscriptionPlan
from app.models.document import DocBlock, Document
from app.models.platform import (
    InviteCode,
    SysAlertLog,
    SysConfig,
    SysDictData,
    SysDictType,
    SysJob,
    SysJobLog,
    SysLoginLog,
    SysMenu,
    SysNotice,
    SysOperLog,
    SysOrg,
    SysRole,
    SysRoleMenu,
    SysStatsDaily,
    SysUserRole,
)
from app.models.project import Project
from app.models.task import LlmCall, Task
from app.models.user import User, VerificationCode

__all__ = [
    # 业务域（MVP）
    "Base", "User", "VerificationCode", "Project", "Document", "DocBlock",
    "CheckItem", "Comparison", "Finding", "Report", "Task", "LlmCall",
    "QuotaAccount", "Order", "AuditLog",
    # 平台域（05 v2.0）
    "SysOrg", "SysRole", "SysUserRole", "SysMenu", "SysRoleMenu",
    "SysConfig", "SysDictType", "SysDictData", "SysNotice",
    "SysJob", "SysJobLog", "SysLoginLog", "SysOperLog", "SysStatsDaily", "SysAlertLog",
    "InviteCode", "Attachment", "LegalDocument", "UserAgreement",
    "AiModelConfig", "PromptTemplate",
    # 商业化域（P2）
    "Payment", "SubscriptionPlan", "Subscription", "RuleSet", "RuleItem",
]
