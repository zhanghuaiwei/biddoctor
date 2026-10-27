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


# ============================================================================
# 以下为平台化域枚举（05-平台化管理与运维设计 v2.0）：sys_* / 附件 / 法务 / AI 治理
# ============================================================================


class DataScope(StrEnum):
    """角色数据权限范围（05 §2.1）：SaaS 仅用 all/self 两档，org 为私有化预留。"""

    ALL = "all"
    ORG = "org"
    SELF = "self"


class CommonStatus(StrEnum):
    """平台域通用启停状态（sys_org/sys_role/sys_menu/sys_dict_data）。"""

    ACTIVE = "active"
    DISABLED = "disabled"


class MenuType(StrEnum):
    """sys_menu 节点类型（05 §2.3）：目录/页面/按钮权限点。"""

    DIR = "dir"
    MENU = "menu"
    BUTTON = "button"


class ConfigValueType(StrEnum):
    """sys_config.value_type：值反序列化方式。"""

    STR = "str"
    INT = "int"
    BOOL = "bool"
    JSON = "json"


class NoticeType(StrEnum):
    """sys_notice.type。"""

    NOTICE = "notice"
    ANNOUNCEMENT = "announcement"


class NoticeLevel(StrEnum):
    """sys_notice.level 与 sys_alert_log.level 共用分级。"""

    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"


class NoticeStatus(StrEnum):
    """sys_notice 状态机：draft → published（publish_at 生效）→ offline。"""

    DRAFT = "draft"
    PUBLISHED = "published"
    OFFLINE = "offline"


class LoginResult(StrEnum):
    """sys_login_log.result：登录尝试全量记录（与 audit_logs 分工）。"""

    SUCCESS = "success"
    FAIL = "fail"


class AlertRuleKey(StrEnum):
    """告警规则键（sys_config alert.* 键，05 §4）：触发时落 sys_alert_log.rule_key。"""

    TASK_FAIL_RATE = "alert.task_fail_rate"
    PENDING_BACKLOG = "alert.pending_backlog_min"
    DISK_USAGE = "alert.disk_usage"
    COST_PER_PROJECT = "alert.cost_per_project"
    JOB_CONSECUTIVE_FAIL = "alert.job_consecutive_fail"
    RECONCILE_DIFF = "alert.reconcile_diff"
    LLM_CIRCUIT = "alert.llm_circuit"


class AttachmentModule(StrEnum):
    """attachments.module 白名单（05 §7）：documents（标书原件）保持独立不迁移。"""

    ORDER_VOUCHER = "order_voucher"  # 订单支付凭证截图
    APPEAL = "appeal"  # 申诉材料
    IMPORT = "import"  # 批量导入
    PROFILE = "profile"  # 资料补传


class LegalDocType(StrEnum):
    """legal_documents.doc_type：三类法务文档（05 §8）。"""

    USER_AGREEMENT = "user_agreement"
    PRIVACY_POLICY = "privacy_policy"
    DISCLAIMER = "disclaimer"


class LegalStatus(StrEnum):
    """legal_documents 版本状态机：draft → effective → retired。"""

    DRAFT = "draft"
    EFFECTIVE = "effective"
    RETIRED = "retired"


class PaymentChannel(StrEnum):
    """payments.channel（P2 自助支付预留；当前人工核销不产生记录）。"""

    WECHAT_NATIVE = "wechat_native"
    ALIPAY_QR = "alipay_qr"
    WECHAT_H5 = "wechat_h5"


class PaymentStatus(StrEnum):
    """payments.status（P2）：渠道侧支付流水状态机。"""

    CREATED = "created"
    PAYING = "paying"
    PAID = "paid"
    FAILED = "failed"
    CLOSED = "closed"
    REFUNDED = "refunded"


class PlanStatus(StrEnum):
    """subscription_plans.status：active 可售，retired 停售（存量不受影响）。"""

    ACTIVE = "active"
    RETIRED = "retired"


class SubscriptionStatus(StrEnum):
    """subscriptions.status：active → expired（period_end 到期）/ cancelled。"""

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RuleSetStatus(StrEnum):
    """rule_sets 版本状态机：draft → active（同法版本仅一版 active）→ retired。"""

    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class RuleKind(StrEnum):
    """rule_items.kind：规则表达式类型（注入 extractor 预筛 / comparator 复核）。"""

    REGEX = "regex"
    KEYWORD = "keyword"
    NUMERIC = "numeric"
    DATE = "date"


class RuleAction(StrEnum):
    """rule_items.action：hint=预筛召回；must=强制核对；veto=可推翻 LLM 满足判定。"""

    HINT = "hint"
    MUST = "must"
    VETO = "veto"


class AiPurpose(StrEnum):
    """ai_model_config.purpose：模型用途映射（02 §7 重/轻两档 + 向量）。"""

    HEAVY = "heavy"
    LIGHT = "light"
    EMBED = "embed"


class LlmPurpose(StrEnum):
    """llm_calls.purpose：调用场景记账维度。"""

    EXTRACT = "extract"
    JUDGE = "judge"
    SUMMARY = "summary"
    RETRY = "retry"
    EMBED = "embed"
