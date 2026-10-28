"""平台域契约（05 §10 /api/admin/* + 用户端公告/法务/附件/me）：请求与响应模型。

约定与全站一致：分页 limit/offset + total；金额 Decimal→字符串；枚举引用注册表；
审计/告警的 detail/metric 快照用 dict[str, Any]（结构随指标演进，不强锁）。
"""

import uuid as _uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

# ── 通用 ─────────────────────────────────────────────────────────────────────


class OkOut(BaseModel):
    ok: bool = True


# ── 机构 ─────────────────────────────────────────────────────────────────────


class OrgIn(BaseModel):
    name: str
    parent_id: int | None = None
    code: str | None = None
    sort: int = 0
    leader: str | None = None


class OrgUpdate(BaseModel):
    name: str | None = None
    parent_id: int | None = None
    code: str | None = None
    sort: int | None = None
    leader: str | None = None
    status: str | None = None  # active | disabled


class OrgNode(BaseModel):
    id: int
    parent_id: int | None
    name: str
    code: str | None
    sort: int
    leader: str | None
    status: str
    children: list["OrgNode"] = []


# ── 角色 / 菜单 / RBAC ───────────────────────────────────────────────────────


class RoleOut(BaseModel):
    id: int
    code: str
    name: str
    data_scope: str
    sort: int
    status: str
    remark: str | None

    model_config = ConfigDict(from_attributes=True)


class MenuOut(BaseModel):
    id: int
    parent_id: int | None
    name: str
    type: str
    path: str | None
    component: str | None
    perm: str | None
    icon: str | None
    sort: int
    visible: bool
    status: str

    model_config = ConfigDict(from_attributes=True)


class MenuUpdate(BaseModel):
    name: str | None = None
    path: str | None = None
    component: str | None = None
    perm: str | None = None
    icon: str | None = None
    sort: int | None = None
    visible: bool | None = None
    status: str | None = None


class MenuNode(BaseModel):
    id: int
    parent_id: int | None
    name: str
    type: str
    path: str | None
    component: str | None
    icon: str | None
    sort: int
    visible: bool
    children: list["MenuNode"] = []


class MeMenusOut(BaseModel):
    """当前用户导航数据：菜单树 + 权限点集合（前端按钮级过滤数据源）。"""

    menus: list[MenuNode]
    perms: list[str]


class UserRolesIn(BaseModel):
    role_ids: list[int]


class RoleMenusIn(BaseModel):
    menu_ids: list[int]


# ── 用户管理 ─────────────────────────────────────────────────────────────────


class AdminUserOut(BaseModel):
    id: int
    email: str
    nickname: str | None
    role: str
    status: str
    org_id: int | None
    org_name: str | None = None
    created_at: datetime
    last_login_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AdminUserPage(BaseModel):
    items: list[AdminUserOut]
    total: int


class UserRolesOut(BaseModel):
    roles: list[RoleOut]


# ── 邀请码 ───────────────────────────────────────────────────────────────────


class InviteIssueIn(BaseModel):
    max_uses: int = 1
    ttl_days: int = 30  # 0 = 永不过期


class InviteOut(BaseModel):
    id: int
    code: str
    max_uses: int
    used_count: int
    expires_at: datetime | None
    created_by: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvitePage(BaseModel):
    items: list[InviteOut]
    total: int


# ── 参数配置 ─────────────────────────────────────────────────────────────────


class ConfigOut(BaseModel):
    id: int
    config_key: str
    value: str
    value_type: str
    name: str
    remark: str | None
    updated_by: int | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConfigUpdateIn(BaseModel):
    value: str


# ── 字典 ─────────────────────────────────────────────────────────────────────


class DictTypeOut(BaseModel):
    id: int
    dict_type: str
    name: str
    remark: str | None

    model_config = ConfigDict(from_attributes=True)


class DictTypeIn(BaseModel):
    dict_type: str
    name: str
    remark: str | None = None


class DictDataOut(BaseModel):
    id: int
    dict_type: str
    value: str
    label: str
    sort: int
    extra: dict[str, Any] | None
    status: str

    model_config = ConfigDict(from_attributes=True)


class DictDataIn(BaseModel):
    value: str
    label: str
    sort: int = 0
    extra: dict[str, Any] | None = None


class DictDataUpdate(BaseModel):
    label: str | None = None
    sort: int | None = None
    extra: dict[str, Any] | None = None
    status: str | None = None


# ── 公告 ─────────────────────────────────────────────────────────────────────


class NoticeIn(BaseModel):
    title: str
    content: str
    type: str = "notice"
    level: str = "info"
    publish_at: datetime | None = None  # 预约发布时间


class NoticeOut(BaseModel):
    id: int
    title: str
    content: str
    type: str
    level: str
    publish_at: datetime | None
    status: str
    created_by: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NoticePage(BaseModel):
    items: list[NoticeOut]
    total: int


# ── 定时任务 ─────────────────────────────────────────────────────────────────


class JobOut(BaseModel):
    id: int
    job_key: str
    name: str
    cron_expr: str
    handler: str
    enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    remark: str | None

    model_config = ConfigDict(from_attributes=True)


class JobLogOut(BaseModel):
    id: int
    job_key: str
    status: str
    cost_ms: int | None
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobLogPage(BaseModel):
    items: list[JobLogOut]
    total: int


# ── 告警 ─────────────────────────────────────────────────────────────────────


class AlertOut(BaseModel):
    id: int
    rule_key: str
    level: str
    title: str
    content: str | None
    metric: dict[str, Any] | None
    acked_by: int | None
    acked_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertPage(BaseModel):
    items: list[AlertOut]
    total: int
    unacked: int


# ── 日志三表 ─────────────────────────────────────────────────────────────────


class AuditLogOut(BaseModel):
    id: int
    user_id: int | None
    user_email: str | None = None
    action: str
    target: str | None
    detail: dict[str, Any]
    ip: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    total: int


class LoginLogOut(BaseModel):
    id: int
    user_id: int | None
    email: str | None
    result: str
    fail_reason: str | None
    ip: str | None
    user_agent: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoginLogPage(BaseModel):
    items: list[LoginLogOut]
    total: int


class OperLogOut(BaseModel):
    id: int
    user_id: int | None
    module: str
    action: str
    method: str | None
    path: str | None
    status_code: int | None
    cost_ms: int | None
    request: dict[str, Any] | None
    ip: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OperLogPage(BaseModel):
    items: list[OperLogOut]
    total: int


# ── 统计 / 监控 ──────────────────────────────────────────────────────────────


class StatRowOut(BaseModel):
    stat_date: date
    dim: str
    metric: str
    value_num: Decimal
    dims: dict[str, Any] | None

    model_config = ConfigDict(from_attributes=True)


class MonitorOverviewOut(BaseModel):
    """监控大盘（05 §4.1 表 2）：任务/LLM/容量聚合 + 未确认告警数。"""

    tasks: dict[str, Any]
    llm: dict[str, Any]
    capacity: dict[str, Any]
    unacked_alerts: int


class TaskAdminOut(BaseModel):
    id: int
    type: str
    status: str
    stage: str | None
    progress: int
    attempt: int
    error_code: str | None
    error_msg: str | None
    project_id: int | None
    document_id: int | None
    comparison_id: int | None
    created_at: datetime
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TaskAdminPage(BaseModel):
    items: list[TaskAdminOut]
    total: int


# ── 附件 ─────────────────────────────────────────────────────────────────────


class AttachmentOut(BaseModel):
    id: int
    uuid: _uuid.UUID
    module: str
    business_id: int | None
    orig_name: str
    content_type: str | None
    size_bytes: int
    uploaded_by: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttachmentPage(BaseModel):
    items: list[AttachmentOut]
    total: int


# ── 法务 ─────────────────────────────────────────────────────────────────────


class LegalDocOut(BaseModel):
    id: int
    doc_type: str
    version: str
    title: str
    content: str
    effective_at: datetime
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LegalDocIn(BaseModel):
    doc_type: str
    version: str
    title: str
    content: str
    effective_at: datetime


class LegalCurrentOut(BaseModel):
    """用户端当前生效版列表（signatures=本人已签署版本 id 集合）。"""

    documents: list[LegalDocOut]
    signed_ids: list[int]


class SignatureOut(BaseModel):
    id: int
    user_id: int
    user_email: str | None = None
    legal_doc_id: int
    ip: str | None
    signed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SignaturePage(BaseModel):
    items: list[SignatureOut]
    total: int


# ── AI 治理 ──────────────────────────────────────────────────────────────────


class AiModelOut(BaseModel):
    id: int
    model_code: str
    provider: str
    purpose: str
    input_price: Decimal
    output_price: Decimal
    rpm_limit: int | None
    enabled: bool
    remark: str | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AiModelIn(BaseModel):
    model_code: str
    provider: str = "zhipu"
    purpose: str
    input_price: Decimal = Decimal("0")
    output_price: Decimal = Decimal("0")
    rpm_limit: int | None = None
    enabled: bool = True
    remark: str | None = None


class AiModelUpdate(BaseModel):
    purpose: str | None = None
    input_price: Decimal | None = None
    output_price: Decimal | None = None
    rpm_limit: int | None = None
    enabled: bool | None = None
    remark: str | None = None


class PromptOut(BaseModel):
    id: int
    name: str
    purpose: str
    version: int
    template: str
    variables: dict[str, Any] | None
    is_active: bool
    eval_score: dict[str, Any] | None
    updated_by: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptIn(BaseModel):
    name: str
    purpose: str
    version: int
    template: str
    variables: dict[str, Any] | None = None


# ── 订阅 / 规则库 ────────────────────────────────────────────────────────────


class PlanOut(BaseModel):
    id: int
    code: str
    name: str
    price_cny: Decimal
    period_months: int
    compare_quota: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class PlanIn(BaseModel):
    code: str
    name: str
    price_cny: Decimal
    period_months: int = 1
    compare_quota: int


class PlanUpdate(BaseModel):
    name: str | None = None
    price_cny: Decimal | None = None
    status: str | None = None


class SubscriptionOut(BaseModel):
    id: int
    user_id: int
    user_email: str | None = None
    plan_id: int
    plan_code: str | None = None
    status: str
    period_start: datetime
    period_end: datetime
    auto_renew: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionPage(BaseModel):
    items: list[SubscriptionOut]
    total: int


class RuleSetOut(BaseModel):
    id: int
    industry: str
    law_version: str
    version: int
    status: str
    effective_from: datetime | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RuleSetIn(BaseModel):
    industry: str
    law_version: str
    notes: str | None = None


class RuleItemOut(BaseModel):
    id: int
    rule_set_id: int
    category: str
    kind: str
    pattern: str
    action: str
    weight: Decimal
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class RuleItemIn(BaseModel):
    category: str
    kind: str
    pattern: str
    action: str = "hint"
    weight: Decimal = Decimal("1.00")
    description: str | None = None


# ── 支付流水（P2 预留，只读）────────────────────────────────────────────────


class PaymentOut(BaseModel):
    id: int
    order_id: int
    channel: str
    out_trade_no: str
    amount_cny: Decimal
    status: str
    paid_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentPage(BaseModel):
    items: list[PaymentOut]
    total: int
