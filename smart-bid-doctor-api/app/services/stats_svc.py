"""统计报表（sys_stats_daily，05 §6）：T+1 汇总（stats_rollup job 每日 01:30）+
即席查询。明细实时聚合不建表；本表供报表页与趋势图。

维度清单（05 §6.2 表 3）：user / business / commerce / cost / quality / system。
LLM 相关指标在 M1 接入前自然为 0（llm_calls 空表），上线后自动出数。
"""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import (
    Document,
    LlmCall,
    Order,
    Project,
    Subscription,
    SysJobLog,
    SysOrg,
    SysStatsDaily,
    Task,
    User,
)


def rollup_day(db: Session, day: dt.date) -> dict:
    """汇总指定自然日（UTC 日界）→ 覆盖式写入（重跑幂等）。返回写入行数摘要。"""
    day_start = dt.datetime(day.year, day.month, day.day, tzinfo=dt.UTC)
    day_end = day_start + dt.timedelta(days=1)
    now7 = day_end + dt.timedelta(days=7)

    rows: list[SysStatsDaily] = []

    def put(dim: str, metric: str, value: float, dims: dict | None = None):
        rows.append(SysStatsDaily(
            stat_date=day, dim=dim, metric=metric,
            value_num=round(float(value or 0), 4), dims=dims,
        ))

    # ── user 域 ──
    put("user", "registered_users",
        db.query(func_count(User.id)).filter(
            User.created_at >= day_start, User.created_at < day_end).scalar() or 0)
    active = db.query(sa.func.count(sa.distinct(Project.user_id))).filter(
        Project.created_at >= day_end - dt.timedelta(days=7),
        Project.created_at < now7).scalar() or 0
    put("user", "active_users_7d", active)
    put("user", "orgs_count",
        db.query(func_count(SysOrg.id)).filter(SysOrg.deleted_at.is_(None)).scalar() or 0)

    # ── business 域 ──
    put("business", "projects_created",
        db.query(func_count(Project.id)).filter(
            Project.created_at >= day_start, Project.created_at < day_end).scalar() or 0)
    put("business", "checklist_done",
        db.query(func_count(Task.id)).filter(
            Task.type == "checklist", Task.status == "succeeded",
            Task.finished_at >= day_start, Task.finished_at < day_end).scalar() or 0)
    put("business", "compare_done",
        db.query(func_count(Task.id)).filter(
            Task.type == "compare", Task.status == "succeeded",
            Task.finished_at >= day_start, Task.finished_at < day_end).scalar() or 0)
    pages = db.query(sa.func.sum(Document.total_pages)).filter(
        Document.created_at >= day_start, Document.created_at < day_end).scalar()
    put("business", "pages_processed", pages or 0)
    scanned = db.query(sa.func.avg(Document.is_scanned_ratio)).filter(
        Document.created_at >= day_start, Document.created_at < day_end,
        Document.is_scanned_ratio.is_not(None)).scalar()
    put("business", "scanned_ratio_avg", scanned or 0)

    # ── commerce 域（P2 起有值）──
    put("commerce", "orders_created",
        db.query(func_count(Order.id)).filter(
            Order.created_at >= day_start, Order.created_at < day_end).scalar() or 0)
    put("commerce", "orders_granted",
        db.query(func_count(Order.id)).filter(
            Order.status == "granted", Order.granted_at >= day_start,
            Order.granted_at < day_end).scalar() or 0)
    gmv = db.query(sa.func.sum(Order.amount_cny)).filter(
        Order.status == "granted", Order.granted_at >= day_start,
        Order.granted_at < day_end).scalar()
    put("commerce", "gmv_cny", gmv or 0)
    put("commerce", "subs_active",
        db.query(func_count(Subscription.id)).filter(
            Subscription.status == "active").scalar() or 0)

    # ── cost 域（按 model/purpose 细分写入 dims）──
    cost_rows = db.execute(
        sa.select(
            LlmCall.model, LlmCall.purpose,
            sa.func.sum(LlmCall.prompt_tokens), sa.func.sum(LlmCall.output_tokens),
            sa.func.sum(LlmCall.cost_cny),
        ).filter(LlmCall.created_at >= day_start, LlmCall.created_at < day_end)
        .group_by(LlmCall.model, LlmCall.purpose)
    ).all()
    tok_p = tok_o = cost_total = 0.0
    for model, purpose, p_tok, o_tok, cost in cost_rows:
        tok_p += p_tok or 0
        tok_o += o_tok or 0
        cost_total += float(cost or 0)
        put("cost", "token_cost_cny", cost or 0, {"model": model, "purpose": purpose})
    put("cost", "token_prompt", tok_p)
    put("cost", "token_output", tok_o)
    put("cost", "token_cost_cny", cost_total)

    # ── quality 域 ──
    total_t = db.query(func_count(Task.id)).filter(
        Task.created_at >= day_start, Task.created_at < day_end,
        Task.type != "purge").scalar() or 0
    ok_t = db.query(func_count(Task.id)).filter(
        Task.created_at >= day_start, Task.created_at < day_end,
        Task.type != "purge", Task.status == "succeeded").scalar() or 0
    nr_t = db.query(func_count(Task.id)).filter(
        Task.created_at >= day_start, Task.created_at < day_end,
        Task.type != "purge", Task.status == "need_review").scalar() or 0
    put("quality", "task_success_rate", ok_t / total_t if total_t else 0)
    put("quality", "need_review_rate", nr_t / total_t if total_t else 0)

    # ── system 域 ──
    put("system", "job_fail_count",
        db.query(func_count(SysJobLog.id)).filter(
            SysJobLog.status == "fail", SysJobLog.created_at >= day_start,
            SysJobLog.created_at < day_end).scalar() or 0)
    put("system", "pending_backlog_peak",
        db.query(func_count(Task.id)).filter(
            Task.status == "pending",
            Task.created_at < day_end).scalar() or 0)

    # 覆盖式写入（重跑幂等）：先删后插，同事务
    db.query(SysStatsDaily).filter(SysStatsDaily.stat_date == day).delete()
    db.add_all(rows)
    db.commit()
    return {"stat_date": day.isoformat(), "rows": len(rows)}


def func_count(col):
    return sa.func.count(col)


def query_daily(db: Session, *, dim: str | None, metric: str | None,
                from_: dt.date | None, to: dt.date | None) -> list[SysStatsDaily]:
    q = db.query(SysStatsDaily)
    if dim:
        q = q.filter(SysStatsDaily.dim == dim)
    if metric:
        q = q.filter(SysStatsDaily.metric == metric)
    if from_:
        q = q.filter(SysStatsDaily.stat_date >= from_)
    if to:
        q = q.filter(SysStatsDaily.stat_date <= to)
    return q.order_by(SysStatsDaily.stat_date.asc(), SysStatsDaily.dim.asc(),
                      SysStatsDaily.metric.asc()).limit(5000).all()


def export_daily(db: Session, *, dim: str | None, metric: str | None,
                 from_: dt.date | None, to: dt.date | None) -> bytes:
    from app.services.log_svc import rows_to_csv

    rows = query_daily(db, dim=dim, metric=metric, from_=from_, to=to)
    return rows_to_csv(
        ["stat_date", "dim", "metric", "value_num", "dims"],
        [[r.stat_date.isoformat(), r.dim, r.metric, str(r.value_num),
          str(r.dims) if r.dims else ""] for r in rows],
    )
