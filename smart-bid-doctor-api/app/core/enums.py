"""业务枚举注册表：状态/角色/类型取值一律引用此处常量，禁止散落字面量。

约定：
- 与 03-数据库设计 §3「枚举与取值域汇总」一一对应，新增取值先改这里再同步文档与迁移；
- 用 StrEnum：成员即 str，SQLAlchemy String 列零转换（模型列注解保持 Mapped[str]，
  避免 SQLAlchemy 按注解推断出 Enum DDL）、JSON 序列化即字符串值、Pydantic 直接做校验。
"""

import enum


class StrEnum(enum.StrEnum):
    """Python 3.12 自带 enum.StrEnum，这里收敛导入点，便于统一扩展。"""


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class UserStatus(StrEnum):
    ACTIVE = "active"
    BANNED = "banned"


class VerificationChannel(StrEnum):
    """验证码通道（verification_codes.channel）：MVP 仅邮箱，短信待主体注册（01·D8）。"""

    EMAIL = "email"
    SMS = "sms"


class Industry(StrEnum):
    GENERAL = "general"
    MEDICAL = "medical"  # P2 医疗器械行业包（01 §3）


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    TENDER_PARSING = "tender_parsing"
    CHECKLIST_READY = "checklist_ready"
    COMPARING = "comparing"
    REPORT_READY = "report_ready"
    ARCHIVED = "archived"


class DocumentRole(StrEnum):
    TENDER = "tender"
    BID = "bid"


class ParseStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    NEED_REVIEW = "need_review"


class EmbeddingStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


class TaskType(StrEnum):
    PARSE = "parse"
    EXTRACT = "extract"
    EMBED = "embed"
    CHECKLIST = "checklist"
    COMPARE = "compare"
    PURGE = "purge"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NEED_REVIEW = "need_review"
    CANCELLED = "cancelled"


class ComparisonStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    NEED_REVIEW = "need_review"


class OrderStatus(StrEnum):
    PENDING = "pending"
    GRANTED = "granted"
    EXPIRED = "expired"
    REFUNDED = "refunded"


class ReportKind(StrEnum):
    CHECKLIST = "checklist"
    COMPARISON = "comparison"


class CheckCategory(StrEnum):
    """条款五分类（02 §3.1）：抽取引擎与清单展示共用。"""

    QUALIFICATION = "qualification"
    COMPLIANCE = "compliance"
    STAR = "star"
    PRICE = "price"
    FORMAT_SEAL = "format_seal"


class Verdict(StrEnum):
    """双文件对照判定（02 §4.2）：不确定一律 uncertain 标黄，绝不输出「满足」。"""

    SATISFIED = "satisfied"
    DEVIATED = "deviated"
    MISSING = "missing"
    UNCERTAIN = "uncertain"


class RiskLevel(StrEnum):
    """报告分级（02 §6.1）：红/黄/绿。"""

    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
