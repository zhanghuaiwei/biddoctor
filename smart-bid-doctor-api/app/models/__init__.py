"""ORM 模型汇总出口（DDL 唯一来源，对应 03-数据库设计 §2 全部表）。

改任何模型 → `alembic revision --autogenerate` 生成迁移（迁移只加不删）；
业务代码统一 `from app.models import X` 引用，不深入子模块导入。
"""

from app.models.audit import AuditLog
from app.models.base import Base
from app.models.billing import Order, QuotaAccount
from app.models.check import CheckItem, Comparison, Finding, Report
from app.models.document import DocBlock, Document
from app.models.project import Project
from app.models.task import LlmCall, Task
from app.models.user import User, VerificationCode

__all__ = [
    "Base", "User", "VerificationCode", "Project", "Document", "DocBlock",
    "CheckItem", "Comparison", "Finding", "Report", "Task", "LlmCall",
    "QuotaAccount", "Order", "AuditLog",
]
