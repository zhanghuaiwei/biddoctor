"""审计日志：写失败不阻断主业务（审计与业务解耦，失败仅记服务端日志）。

留痕规范（skill: smart-bid-doctor-engineering）：所有审计 detail 自动关联 request_id，
使 audit_logs ↔ 结构化日志 ↔ tasks.task_id 可互查，形成功能全生命周期留痕链。
"""

import ipaddress
import logging

from sqlalchemy.orm import Session

from app.core.logging import request_id_var
from app.models import AuditLog

_logger = logging.getLogger("app.audit")


class AuditAction:
    """审计 action 注册表（留痕稳定性：全项目引用常量，禁魔法字符串）。

    新增 action：在此登记 → 按 skill 留痕 checklist 打点 → 同步 skill/AGENTS.md。
    """

    LOGIN = "login"
    UPLOAD = "upload"
    PROJECT_CREATED = "project_created"
    PROJECT_DELETED = "project_deleted"
    ORDER_CREATED = "order_created"
    ORDER_GRANT = "order_grant"  # 03 §2.11 枚举原文
    COMPARE_STARTED = "compare_started"
    DATA_PURGE = "data_purge"
    ADMIN_CREATED = "admin_created"
    ADMIN_PROMOTED = "admin_promoted"
    REPORT_GENERATED = "report_generated"  # 清单/对照报告生成完成
    REPORT_EXPORTED = "report_exported"  # 报告导出（FileResponse）
    REPORT_ACK = "report_ack"  # 报告免责声明确认（disclaimer_ack）
    # ── 平台域（05 §5.2 清单）─────────────────────────────────────────────
    # 系统管理
    SYS_ORG_UPDATE = "sys_org_update"
    SYS_ROLE_GRANT = "sys_role_grant"
    SYS_ROLE_REVOKE = "sys_role_revoke"
    SYS_MENU_UPDATE = "sys_menu_update"
    SYS_USER_BAN = "sys_user_ban"
    SYS_USER_UNBAN = "sys_user_unban"
    SYS_INVITE_ISSUE = "sys_invite_issue"
    # 运维管理
    SYS_CONFIG_UPDATE = "sys_config_update"
    SYS_DICT_UPDATE = "sys_dict_update"
    SYS_NOTICE_PUBLISH = "sys_notice_publish"
    SYS_NOTICE_OFFLINE = "sys_notice_offline"
    SYS_JOB_TOGGLE = "sys_job_toggle"
    SYS_JOB_TRIGGER = "sys_job_trigger"
    # 日志 / 监控
    LOG_EXPORT = "log_export"  # 查询导出（logs/stats CSV 共用）
    ALERT_ACK = "alert_ack"
    # 法务
    LEGAL_PUBLISH = "legal_publish"
    LEGAL_SIGNED = "legal_signed"
    # AI 治理
    AI_MODEL_UPDATE = "ai_model_update"
    AI_PROMPT_SWITCH = "ai_prompt_switch"
    AI_PROMPT_PUBLISH = "ai_prompt_publish"
    # 附件 / 订阅 / 规则库
    ATTACHMENT_DELETE = "attachment_delete"
    ATTACHMENT_UPLOAD = "attachment_upload"
    SUBSCRIPTION_GRANT = "subscription_grant"  # 订阅订单核销激活
    RULESET_UPDATE = "ruleset_update"
    AGREEMENT_SIGNED = "agreement_signed"  # 用户端签署（= legal_signed 用户侧动作）


def _safe_ip(ip: str | None) -> str | None:
    """INET 列只接受合法 IP；非法值（unix socket/testclient 等）归 NULL。"""
    if not ip:
        return None
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None


def log(
    db: Session,
    user_id: int | None,
    action: str,
    target: str | None = None,
    detail: dict | None = None,
    ip: str | None = None,
):
    # detail 自动附带 request_id（无请求上下文时为 "-"）
    payload = {"request_id": request_id_var.get(), **(detail or {})}
    try:
        db.add(
            AuditLog(
                user_id=user_id, action=action, target=target,
                detail=payload, ip=_safe_ip(ip),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        _logger.exception("audit log failed: action=%s target=%s", action, target)
