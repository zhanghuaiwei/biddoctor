"""平台化管理域模型（05-平台化管理与运维设计 v2.0，db DDL §3/§20-34）。

- RBAC：users ─< sys_user_role >─ sys_role ─< sys_role_menu >─ sys_menu（目录/页面/按钮权限点），
  users.role 保留为快速判定位（登录链路零改动），细粒度权限走本域映射表；
- sys_config：运行时可调参数（改值即生效，config_svc 进程内 TTL 缓存）；
- sys_job / sys_job_log：定时任务调度元数据与运行记录（执行仍复用 tasks 队列范式）；
- sys_login_log / sys_oper_log：与 audit_logs 三表分工（05 §5.1）；
- sys_stats_daily：T+1 汇总表（stats_rollup job），明细实时聚合不建表；
- invite_codes：P1 邀测期注册管控预留（消费走原子 UPDATE used_count）。
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PkMixin, TimestampMixin


class SysOrg(Base, PkMixin, TimestampMixin):
    """机构树（05 §2.4）：只做组织归属与权限范围，不做数据隔离（多租户仍为 Out 边界）。"""

    __tablename__ = "sys_org"

    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_org.id"))
    name: Mapped[str] = mapped_column(String(64))
    code: Mapped[str | None] = mapped_column(String(32), unique=True)  # 机构编码
    sort: Mapped[int] = mapped_column(Integer, default=0)
    leader: Mapped[str | None] = mapped_column(String(64))  # 负责人姓名（仅展示）
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | disabled
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SysRole(Base, PkMixin, TimestampMixin):
    """角色（05 §2.2）：super_admin 不可删除/停用；data_scope 为私有化预留。"""

    __tablename__ = "sys_role"

    code: Mapped[str] = mapped_column(String(32), unique=True)  # super_admin | operator | ...
    name: Mapped[str] = mapped_column(String(64))
    data_scope: Mapped[str] = mapped_column(String(16), default="self")  # all | org | self
    sort: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")
    remark: Mapped[str | None] = mapped_column(String(256))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SysUserRole(Base):
    """用户角色映射（复合主键，无时间列——纯关联表）。"""

    __tablename__ = "sys_user_role"
    __table_args__ = (PrimaryKeyConstraint("user_id", "role_id"),)

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_role.id", ondelete="CASCADE"))


class SysMenu(Base, PkMixin, TimestampMixin):
    """菜单与按钮权限点（05 §2.3）：前端静态路由 + 本表驱动导航与按钮权限过滤。"""

    __tablename__ = "sys_menu"

    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_menu.id"))
    name: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(8))  # dir | menu | button
    path: Mapped[str | None] = mapped_column(String(128))  # 前端路由路径（dir/menu）
    component: Mapped[str | None] = mapped_column(String(128))  # 组件标识（menu）
    perm: Mapped[str | None] = mapped_column(String(64))  # 权限点（button），如 admin:order:grant
    icon: Mapped[str | None] = mapped_column(String(32))
    sort: Mapped[int] = mapped_column(Integer, default=0)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="active")


class SysRoleMenu(Base):
    """角色菜单映射（复合主键）。"""

    __tablename__ = "sys_role_menu"
    __table_args__ = (PrimaryKeyConstraint("role_id", "menu_id"),)

    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_role.id", ondelete="CASCADE"))
    menu_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_menu.id", ondelete="CASCADE"))


class SysConfig(Base, PkMixin, TimestampMixin):
    """运行时可调参数（05 §3.1）：quota.free_monthly / alert.* / retain.* 等键。"""

    __tablename__ = "sys_config"

    config_key: Mapped[str] = mapped_column(String(64), unique=True)
    value: Mapped[str] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(String(8), default="str")  # str | int | bool | json
    name: Mapped[str] = mapped_column(String(64))
    remark: Mapped[str | None] = mapped_column(String(256))
    updated_by: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class SysDictType(Base, PkMixin, TimestampMixin):
    """字典类型：仅管展示层（label/排序/颜色），取值域仍以代码枚举注册表为准。"""

    __tablename__ = "sys_dict_type"

    dict_type: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    remark: Mapped[str | None] = mapped_column(String(256))


class SysDictData(Base, PkMixin, TimestampMixin):
    """字典数据：value 与代码注册表一致，extra 承载颜色/图标等展示属性。"""

    __tablename__ = "sys_dict_data"

    dict_type: Mapped[str] = mapped_column(
        String(64), ForeignKey("sys_dict_type.dict_type", ondelete="CASCADE")
    )
    value: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(64))
    sort: Mapped[int] = mapped_column(Integer, default=0)
    extra: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="active")

    __table_args__ = (Index("idx_dict_data_type", "dict_type", "sort"),)


class SysNotice(Base, PkMixin, TimestampMixin):
    """平台公告/维护通知（05 §3.3）：draft → published（publish_at 生效）→ offline。"""

    __tablename__ = "sys_notice"

    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(8), default="notice")  # notice | announcement
    level: Mapped[str] = mapped_column(String(8), default="info")  # info | warn | critical
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SysJob(Base, PkMixin, TimestampMixin):
    """定时任务调度元数据（05 §3.4）：执行触发复用 tasks 队列或 worker 内联执行。"""

    __tablename__ = "sys_job"

    job_key: Mapped[str] = mapped_column(String(32), unique=True)  # purge | stats_rollup | ...
    name: Mapped[str] = mapped_column(String(64))
    cron_expr: Mapped[str] = mapped_column(String(32))
    handler: Mapped[str] = mapped_column(String(64))  # worker 内 job 处理器标识
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remark: Mapped[str | None] = mapped_column(String(256))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class SysJobLog(Base, PkMixin, TimestampMixin):
    """定时任务运行记录：status/cost_ms/result 摘要/error；连续失败触发告警。"""

    __tablename__ = "sys_job_log"

    job_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_job.id", ondelete="SET NULL"))
    job_key: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(8))  # ok | fail
    cost_ms: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("idx_job_log_key", "job_key", "created_at"),)


class SysLoginLog(Base, PkMixin, TimestampMixin):
    """登录尝试全量（05 §5.1）：每次成功/失败都记，与 audit_logs 分工互补。"""

    __tablename__ = "sys_login_log"

    user_id: Mapped[int | None] = mapped_column(BigInteger)
    email: Mapped[str | None] = mapped_column(String(320))
    result: Mapped[str] = mapped_column(String(8))  # success | fail
    fail_reason: Mapped[str | None] = mapped_column(String(32))  # code_invalid | locked | banned
    ip: Mapped[str | None] = mapped_column(String(64))  # INET 语义，写入前 _safe_ip 校验
    user_agent: Mapped[str | None] = mapped_column(String(256))

    __table_args__ = (
        Index("idx_login_log_user", "user_id", "created_at"),
        Index("idx_login_log_time", "created_at"),
    )


class SysOperLog(Base, PkMixin, TimestampMixin):
    """管理端 HTTP 请求级日志（05 §5.1）：仅记 /api/admin/*，敏感字段不入库。"""

    __tablename__ = "sys_oper_log"

    user_id: Mapped[int | None] = mapped_column(BigInteger)
    module: Mapped[str] = mapped_column(String(32))  # admin_user | admin_order | ...
    action: Mapped[str] = mapped_column(String(48))
    method: Mapped[str | None] = mapped_column(String(8))
    path: Mapped[str | None] = mapped_column(String(128))
    status_code: Mapped[int | None] = mapped_column(Integer)
    cost_ms: Mapped[int | None] = mapped_column(Integer)
    request: Mapped[dict | None] = mapped_column(JSONB)  # 请求摘要（query 参数，脱敏后）
    ip: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index("idx_oper_log_user", "user_id", "created_at"),
        Index("idx_oper_log_module", "module", "created_at"),
    )


class SysStatsDaily(Base, PkMixin, TimestampMixin):
    """每日统计汇总（T+1，05 §6）：stats_rollup 每日汇总前一日，供报表页趋势图。"""

    __tablename__ = "sys_stats_daily"

    stat_date: Mapped[date] = mapped_column(Date)
    dim: Mapped[str] = mapped_column(String(32))  # user | business | commerce | cost | quality | system
    metric: Mapped[str] = mapped_column(String(64))
    value_num: Mapped[float] = mapped_column(Numeric(16, 4), default=0)
    dims: Mapped[dict | None] = mapped_column(JSONB)  # 细分维度（model/purpose/industry）

    __table_args__ = (
        # 命名约束 uq_stats_daily 与 db DDL 一致
        Index(
            "uq_stats_daily", "stat_date", "dim", "metric", unique=True,
        ),
        Index("idx_stats_daily_date", "stat_date", "dim"),
    )


class SysAlertLog(Base, PkMixin, TimestampMixin):
    """告警记录（05 §4）：阈值入 sys_config（alert.* 键），触发落本表，人工 ack 闭环。"""

    __tablename__ = "sys_alert_log"

    rule_key: Mapped[str] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(8), default="warn")
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str | None] = mapped_column(Text)
    metric: Mapped[dict | None] = mapped_column(JSONB)  # 触发时的指标快照
    acked_by: Mapped[int | None] = mapped_column(BigInteger)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_alert_log_rule", "rule_key", "created_at"),
        Index("idx_alert_log_ack", "acked_at", postgresql_where=text("acked_at IS NULL")),
    )


class InviteCode(Base, PkMixin, TimestampMixin):
    """邀请码（P1 邀测预留）：注册管控开关入 sys_config；消费走原子 UPDATE used_count。"""

    __tablename__ = "invite_codes"

    code: Mapped[str] = mapped_column(String(16), unique=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
