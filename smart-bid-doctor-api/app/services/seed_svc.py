"""平台种子数据（幂等，bootstrap 迁移后执行）：05 文档 §2/§3 内置配置。

- 内置角色：super_admin（全量）/ operator（业务运营，不含系统管理与 AI 治理）；
- 机构根节点「平台运营部」；菜单树（dir/menu/button 三级，perm 驱动按钮权限）；
- sys_config 默认参数（05 §3.1 键清单 + signup.require_invite）；
- 内置定时任务（purge/stats_rollup/alert_scan/reconcile/daily_report）；
- 法务文档 v1.0（用户协议/隐私政策/免责声明，draft→effective）；
- AI 模型注册（计价快照，M1 接入 LLM 时读取）。

全部步骤存在即跳过，可重复执行。
"""

import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import LegalStatus, PlanStatus
from app.models import (
    AiModelConfig,
    LegalDocument,
    SubscriptionPlan,
    SysConfig,
    SysJob,
    SysMenu,
    SysOrg,
    SysRole,
    SysRoleMenu,
)

_logger = logging.getLogger("app.seed")

SUPER_ADMIN = "super_admin"
OPERATOR = "operator"

# 菜单树：(key, type, name, path, perm, parent_key, sort)
_MENUS: list[tuple[str, str, str, str | None, str | None, str | None, int]] = [
    ("root", "dir", "平台管理", "/admin", None, None, 0),
    ("dashboard", "menu", "监控大盘", "/admin/dashboard", None, "root", 10),
    ("monitor_read", "button", "查看监控", None, "admin:monitor:read", "dashboard", 11),
    ("ops", "dir", "运营管理", "/admin", None, "root", 20),
    ("orders", "menu", "订单管理", "/admin/orders", None, "ops", 21),
    ("order_read", "button", "查看订单", None, "admin:order:read", "orders", 22),
    ("order_grant", "button", "核销订单", None, "admin:order:grant", "orders", 23),
    ("subs", "menu", "订阅管理", "/admin/subs", None, "ops", 24),
    ("sub_all", "button", "订阅管理", None, "admin:sub", "subs", 25),
    ("users", "menu", "用户管理", "/admin/users", None, "ops", 26),
    ("sys_user", "button", "用户管理", None, "admin:sys:user", "users", 27),
    ("tasks", "menu", "任务巡检", "/admin/tasks", None, "ops", 28),
    ("task_read", "button", "查看任务", None, "admin:monitor:read", "tasks", 29),
    ("stats", "menu", "统计报表", "/admin/stats", None, "ops", 30),
    ("stats_read", "button", "查看统计", None, "admin:stats:read", "stats", 31),
    ("attachments", "menu", "附件库", "/admin/attachments", None, "ops", 32),
    ("attachment_all", "button", "附件管理", None, "admin:attachment", "attachments", 33),
    ("sysops", "dir", "运维管理", "/admin", None, "root", 40),
    ("configs", "menu", "参数配置", "/admin/configs", None, "sysops", 41),
    ("sys_config", "button", "参数/字典管理", None, "admin:sys:config", "configs", 42),
    ("dicts", "menu", "字典管理", "/admin/dicts", None, "sysops", 43),
    ("dict_all", "button", "字典管理", None, "admin:sys:config", "dicts", 44),
    ("notices", "menu", "公告管理", "/admin/notices", None, "sysops", 45),
    ("sys_notice", "button", "公告管理", None, "admin:sys:notice", "notices", 46),
    ("jobs", "menu", "定时任务", "/admin/jobs", None, "sysops", 47),
    ("sys_job", "button", "定时任务管理", None, "admin:sys:job", "jobs", 48),
    ("alerts", "menu", "告警中心", "/admin/alerts", None, "sysops", 49),
    ("monitor_alert", "button", "告警管理", None, "admin:monitor:alert", "alerts", 50),
    ("audit", "dir", "日志审计", "/admin", None, "root", 60),
    ("logs_audit", "menu", "审计日志", "/admin/logs-audit", None, "audit", 61),
    ("log_read_a", "button", "日志查看", None, "admin:log:read", "logs_audit", 62),
    ("logs_login", "menu", "登录日志", "/admin/logs-login", None, "audit", 63),
    ("log_read_l", "button", "日志查看", None, "admin:log:read", "logs_login", 64),
    ("logs_oper", "menu", "操作日志", "/admin/logs-oper", None, "audit", 65),
    ("log_read_o", "button", "日志查看", None, "admin:log:read", "logs_oper", 66),
    ("system", "dir", "系统管理", "/admin", None, "root", 80),
    ("orgs", "menu", "机构管理", "/admin/orgs", None, "system", 81),
    ("sys_org", "button", "机构管理", None, "admin:sys:org", "orgs", 82),
    ("roles", "menu", "角色权限", "/admin/roles", None, "system", 83),
    ("sys_role", "button", "角色管理", None, "admin:sys:role", "roles", 84),
    ("sys_menu", "button", "菜单管理", None, "admin:sys:menu", "roles", 85),
    ("legal", "menu", "法务文档", "/admin/legal", None, "system", 86),
    ("admin_legal", "button", "法务管理", None, "admin:legal", "legal", 87),
    ("ai", "menu", "AI 治理", "/admin/ai", None, "system", 88),
    ("admin_ai", "button", "AI 治理", None, "admin:ai", "ai", 89),
    ("rules", "menu", "规则库", "/admin/rules", None, "system", 90),
    ("admin_rule", "button", "规则库管理", None, "admin:rule", "rules", 91),
]

# operator（业务运营）可见权限点：不含系统管理与 AI 治理（05 §2.2 表 0）
OPERATOR_PERMS = {
    "admin:monitor:read", "admin:monitor:alert",
    "admin:order:read", "admin:order:grant", "admin:sub",
    "admin:sys:user", "admin:stats:read", "admin:attachment",
    "admin:sys:notice", "admin:log:read",
}

# 内置定时任务（05 §3.4）：cron 为服务器本地时钟（UTC 容器），purge 换算北京时间
_JOBS = [
    ("purge", "数据生命周期清理", "5 19 * * *", "purge",
     "北京时间每日 03:05；入 tasks 队列执行（唯一 queue 型 job）"),
    ("stats_rollup", "T+1 统计汇总", "30 1 * * *", "stats_rollup",
     "每日 01:30 汇总前一日全维度指标 + 订阅到期清扫"),
    ("alert_scan", "告警阈值巡检", "*/1 * * * *", "alert_scan",
     "每分钟检查失败率/积压/磁盘/连续失败（05 §4）"),
    ("reconcile", "支付对账", "0 */2 * * *", "reconcile",
     "payments↔orders 一致性扫描；P2 自助支付接入后自动出数"),
    ("daily_report", "每日业务报表", "0 8 * * *", "daily_report",
     "昨日运营指标 JSON 落盘（04 §6）"),
]

_CONFIGS = [
    ("quota.free_monthly", "3", "int", "每月免费项目数", "行锁防并发超发"),
    ("alert.task_fail_rate", "0.10", "str", "任务失败率告警线", "当日 failed/finished"),
    ("alert.cost_per_project", "30", "str", "单项目成本告警线（元）", "M1 接入后生效"),
    ("alert.disk_usage", "0.85", "str", "磁盘占用告警线", "0-1 比例"),
    ("alert.pending_backlog_min", "30", "str", "pending 积压告警线（分钟）", ""),
    ("retain.reports_days", "180", "int", "报告留存天数", "03 §5 联动"),
    ("llm.circuit_break_threshold", "5", "int", "LLM 熔断阈值", "02 §7 联动"),
    ("signup.require_invite", "false", "bool", "注册是否需邀请码", "P1 邀测期开启"),
]

_LEGAL_DOCS = [
    ("user_agreement", "v1.0", "用户协议",
     "# 用户协议\n\n"
     "欢迎使用标书废检（smart-bid-doctor）。注册即表示您同意本协议。\n\n"
     "1. **服务性质**：本平台提供投标文件废标风险的辅助自查服务，输出为"
     "「辅助人工复核」参考，不构成任何「保证不废标」承诺，不构成法律意见。\n"
     "2. **账号**：您应妥善保管账号，不得转让、出借；平台可对违规账号采取"
     "限制措施并留痕。\n"
     "3. **付费**：按次套餐与订阅服务经人工核销或在线支付后生效，具体以"
     "下单页展示为准。\n"
     "4. **合规使用**：您承诺不将本服务用于评标辅助、围标串标等违法违规用途，"
     "并遵守所在采购项目的保密要求。\n"
     "5. **免责**：因您未按报告提示进行人工复核导致的损失，平台不承担责任。\n"),
    ("privacy_policy", "v1.0", "隐私政策",
     "# 隐私政策\n\n"
     "本平台遵循《个人信息保护法》最小必要原则处理个人信息。\n\n"
     "1. **收集范围**：仅收集邮箱（登录标识）与操作日志（安全审计必需）；"
     "当前不采集手机号。\n"
     "2. **上传文件**：仅用于本次检查，不用于模型训练，不向第三方提供；"
     "原件与解析产物按留存策略（默认 30 天）自动清理，报告支持阅后即焚。\n"
     "3. **告知-同意**：协议与隐私政策签署记录（时间/IP）留痕可追溯。\n"
     "4. **您的权利**：可申请注销账号（软删+脱敏）、导出或删除个人数据，"
     "联系客服处理。\n"
     "5. **安全**：全站 HTTPS 传输；密钥环境变量管理与定期轮换。\n"),
    ("disclaimer", "v1.0", "免责声明",
     "# 免责声明\n\n"
     "1. 本平台输出为**辅助人工复核工具**，不构成任何「保证不废标」承诺；\n"
     "2. 每条结论均附招标文件原文页码溯源，**高危项须人工确认**后方可作为"
     "投标决策依据；\n"
     "3. AI 生成内容（检查报告/摘要）已按《人工智能生成合成内容标识办法》"
     "添加显式标识；\n"
     "4. 本平台不服务于评标辅助、围标串标检测等违法违规用途；\n"
     "5. 使用本平台即表示您已阅读并理解上述内容。\n"),
]


def run(db: Session) -> dict:
    """执行全部种子（幂等）。返回摘要。"""
    stats: dict[str, int] = {}
    stats["orgs"] = _seed_org(db)
    stats["roles"] = _seed_roles(db)
    stats["menus"] = _seed_menus(db)
    stats["role_menus"] = _seed_role_menus(db)
    stats["configs"] = _seed_configs(db)
    stats["jobs"] = _seed_jobs(db)
    stats["legal"] = _seed_legal(db)
    stats["ai_models"] = _seed_ai_models(db)
    stats["plans"] = _seed_plans(db)
    return stats


def _seed_org(db: Session) -> int:
    if db.query(SysOrg).filter(SysOrg.deleted_at.is_(None)).first():
        return 0
    db.add(SysOrg(name="平台运营部", code="HQ", sort=0))
    db.commit()
    return 1


def _seed_roles(db: Session) -> int:
    n = 0
    seeds = [
        (SUPER_ADMIN, "超级管理员", "all", 0, "平台负责人；不可删除、不可停用"),
        (OPERATOR, "运营", "all", 10, "日常运营人员（订单/用户/任务/统计/日志）"),
    ]
    for code, name, scope, sort, remark in seeds:
        if db.query(SysRole).filter(SysRole.code == code).first() is None:
            db.add(SysRole(code=code, name=name, data_scope=scope, sort=sort, remark=remark))
            n += 1
    db.commit()
    return n


def _seed_menus(db: Session) -> int:
    existing = {m.name: m for m in db.query(SysMenu).all()}
    n = 0
    id_by_key: dict[str, int] = {}
    for key, type_, name, path, perm, _parent_key, sort in _MENUS:
        row = existing.get(name)
        if row is None:
            row = SysMenu(
                name=name, type=type_, path=path, perm=perm, sort=sort,
                visible=True, status="active",
            )
            db.add(row)
            db.flush()
            n += 1
        id_by_key[key] = row.id
    # 父子关系二次遍历（父可能后建）
    for key, _t, _n, _p, _perm, parent_key, _s in _MENUS:
        row = db.get(SysMenu, id_by_key[key])
        want_parent = id_by_key.get(parent_key) if parent_key else None
        if row.parent_id != want_parent:
            row.parent_id = want_parent
    db.commit()
    return n


def _seed_role_menus(db: Session) -> int:
    super_role = db.query(SysRole).filter(SysRole.code == SUPER_ADMIN).first()
    operator_role = db.query(SysRole).filter(SysRole.code == OPERATOR).first()
    n = 0
    all_menu_ids = [m.id for m in db.query(SysMenu).all()]
    if super_role:
        have = {
            rm.menu_id for rm in db.query(SysRoleMenu).filter(
                SysRoleMenu.role_id == super_role.id).all()
        }
        for mid in all_menu_ids:
            if mid not in have:
                db.add(SysRoleMenu(role_id=super_role.id, menu_id=mid))
                n += 1
    if operator_role:
        perm_to_menu = {
            m.perm: m.id for m in db.query(SysMenu).filter(
                SysMenu.perm.is_not(None)).all()
        }
        have = {
            rm.menu_id for rm in db.query(SysRoleMenu).filter(
                SysRoleMenu.role_id == operator_role.id).all()
        }
        for perm in OPERATOR_PERMS:
            mid = perm_to_menu.get(perm)
            if mid and mid not in have:
                db.add(SysRoleMenu(role_id=operator_role.id, menu_id=mid))
                n += 1
    db.commit()
    return n


def _seed_configs(db: Session) -> int:
    n = 0
    for key, value, vtype, name, remark in _CONFIGS:
        if db.query(SysConfig).filter(SysConfig.config_key == key).first() is None:
            db.add(SysConfig(config_key=key, value=value, value_type=vtype,
                             name=name, remark=remark))
            n += 1
    db.commit()
    return n


def _seed_jobs(db: Session) -> int:
    from app.services import job_svc

    n = 0
    for job_key, name, cron_expr, handler, remark in _JOBS:
        if db.query(SysJob).filter(SysJob.job_key == job_key).first() is None:
            db.add(SysJob(
                job_key=job_key, name=name, cron_expr=cron_expr, handler=handler,
                enabled=True, remark=remark,
                next_run_at=job_svc.next_run(cron_expr, dt.datetime.now(dt.UTC)),
            ))
            n += 1
    db.commit()
    return n


def _seed_legal(db: Session) -> int:
    n = 0
    for doc_type, version, title, content in _LEGAL_DOCS:
        exists = db.query(LegalDocument).filter(
            LegalDocument.doc_type == doc_type,
            LegalDocument.version == version,
        ).first()
        if exists is None:
            db.add(LegalDocument(
                doc_type=doc_type, version=version, title=title, content=content,
                effective_at=dt.datetime.now(dt.UTC), status=LegalStatus.EFFECTIVE,
            ))
            n += 1
    db.commit()
    return n


def _seed_ai_models(db: Session) -> int:
    s = get_settings()
    n = 0
    seeds = [
        (s.llm_model_heavy, "heavy", 4.0, 14.0, "重任务（抽取/判定）计价快照"),
        (s.llm_model_light, "light", 0.2, 0.8, "轻任务（分类/兜底）计价快照"),
    ]
    for code, purpose, in_p, out_p, remark in seeds:
        if db.query(AiModelConfig).filter(AiModelConfig.model_code == code).first() is None:
            db.add(AiModelConfig(
                model_code=code, provider="zhipu", purpose=purpose,
                input_price=in_p, output_price=out_p, enabled=True, remark=remark,
            ))
            n += 1
    db.commit()
    return n


def _seed_plans(db: Session) -> int:
    """订阅计划：框架示例（停售状态，运营在管理端启用/改价后上架）。"""
    n = 0
    seeds = [
        ("sub_basic", "基础订阅（月）", 299, 1, 20),
        ("sub_pro", "专业订阅（月）", 799, 1, 60),
    ]
    for code, name, price, months, quota in seeds:
        if db.query(SubscriptionPlan).filter(SubscriptionPlan.code == code).first() is None:
            db.add(SubscriptionPlan(
                code=code, name=name, price_cny=price,
                period_months=months, compare_quota=quota, status=PlanStatus.RETIRED,
            ))
            n += 1
    db.commit()
    return n
