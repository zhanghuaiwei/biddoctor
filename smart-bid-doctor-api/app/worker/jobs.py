"""平台内置定时任务（05 §3.4 / §4）：sys_job 驱动的调度与 inline 执行器。

调度：sys_job 行存 cron 元数据；runner 主循环每轮 tick()——到期 job 原子认领
（job_svc.claim 把 next_run_at 推进到下一周期），queue 型（purge）入 tasks 队列，
inline 型直接执行并写 sys_job_log。管理端启停/手动触发只改元数据，不破坏任务状态机。
"""

import datetime as dt
import json
import logging
import os

import sqlalchemy as sa

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.enums import NoticeLevel
from app.models import Order, Payment, SysJobLog, Task
from app.services import (
    alert_svc,
    config_svc,
    job_svc,
    metrics_svc,
    monitor_svc,
    stats_svc,
    subscription_svc,
)

log = logging.getLogger("worker.jobs")

# tick 节流：主循环 3s 一轮，sys_job 扫描 15s 一次足够（分钟级 cron）
_TICK_INTERVAL = 15.0
_last_tick = 0.0


# ── inline job 实现（注册进 job_svc.INLINE_JOBS）────────────────────────────


@job_svc.register_inline("stats_rollup")
def stats_rollup(db) -> dict:
    """T+1 汇总（每日 01:30）：前一日全维度指标 + 订阅到期清扫。"""
    yesterday = (dt.datetime.now(dt.UTC) - dt.timedelta(days=1)).date()
    rolled = stats_svc.rollup_day(db, yesterday)
    expired = subscription_svc.sweep_expired(db)
    return {**rolled, "subscriptions_expired": expired}


@job_svc.register_inline("alert_scan")
def alert_scan(db) -> dict:
    """阈值巡检（每分钟）：任务失败率 / 积压 / 磁盘 / 定时任务连续失败。

    触发写 sys_alert_log（同规则未确认去抖）；未启用的规则键跳过。
    """
    triggered: list[str] = []
    now = dt.datetime.now(dt.UTC)
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 1) 当日任务失败率（不含 purge/pending/running 在途）
    if config_svc.get_raw(db, "alert.task_fail_rate") is not None:
        threshold = config_svc.get_float(db, "alert.task_fail_rate", 0.10)
        finished = (
            db.query(sa.func.count(Task.id))
            .filter(Task.created_at >= today0, Task.type != "purge",
                    Task.status.in_(["succeeded", "failed", "need_review"]))
            .scalar() or 0
        )
        failed = (
            db.query(sa.func.count(Task.id))
            .filter(Task.created_at >= today0, Task.type != "purge",
                    Task.status == "failed")
            .scalar() or 0
        )
        rate = failed / finished if finished else 0
        if finished >= 10 and rate > threshold:
            if alert_svc.trigger_if_needed(
                db, rule_key="alert.task_fail_rate", level=NoticeLevel.CRITICAL,
                title=f"当日任务失败率 {rate:.0%} 超过阈值 {threshold:.0%}",
                content=f"finished={finished} failed={failed}",
                metric={"rate": rate, "threshold": threshold, "finished": finished},
            ):
                triggered.append("alert.task_fail_rate")

    # 2) pending 积压（最老 pending 任务年龄，分钟）
    if config_svc.get_raw(db, "alert.pending_backlog_min") is not None:
        threshold = config_svc.get_float(db, "alert.pending_backlog_min", 30)
        oldest = (
            db.query(Task.created_at)
            .filter(Task.status == "pending")
            .order_by(Task.created_at.asc())
            .first()
        )
        age_min = (now - oldest[0]).total_seconds() / 60 if oldest else 0
        if age_min > threshold:
            if alert_svc.trigger_if_needed(
                db, rule_key="alert.pending_backlog_min", level=NoticeLevel.WARN,
                title=f"任务积压 {int(age_min)} 分钟超过阈值 {int(threshold)} 分钟",
                content=f"oldest_pending_age_min={int(age_min)}",
                metric={"age_min": round(age_min, 1), "threshold": threshold},
            ):
                triggered.append("alert.pending_backlog_min")

    # 3) 磁盘占用率
    if config_svc.get_raw(db, "alert.disk_usage") is not None:
        threshold = config_svc.get_float(db, "alert.disk_usage", 0.85)
        usage = monitor_svc.disk_usage(db)
        ratio = usage.get("usage_ratio")
        if ratio is not None and ratio > threshold:
            if alert_svc.trigger_if_needed(
                db, rule_key="alert.disk_usage", level=NoticeLevel.CRITICAL,
                title=f"磁盘占用 {ratio:.0%} 超过阈值 {threshold:.0%}",
                content=f"free_mb={usage.get('free_mb')}",
                metric={"usage_ratio": ratio, "threshold": threshold},
            ):
                triggered.append("alert.disk_usage")

    # 4) 定时任务连续 2 次失败
    recent = (
        db.query(SysJobLog)
        .order_by(SysJobLog.id.desc())
        .limit(50)
        .all()
    )
    by_job: dict[str, list[str]] = {}
    for r in recent:
        by_job.setdefault(r.job_key, []).append(r.status)
    for job_key, statuses in by_job.items():
        if statuses[:2] == ["fail", "fail"]:
            if alert_svc.trigger_if_needed(
                db, rule_key="alert.job_consecutive_fail", level=NoticeLevel.WARN,
                title=f"定时任务 {job_key} 连续 2 次失败",
                content="详见管理端定时任务运行历史",
                metric={"job_key": job_key},
            ):
                triggered.append(f"job_consecutive_fail:{job_key}")

    return {"triggered": triggered, "checked": 4}


@job_svc.register_inline("reconcile")
def reconcile(db) -> dict:
    """支付对账（02 §14.2 预留）：payments.paid 与订单核销状态一致性扫描。

    当前人工核销模式不产生 payments 记录，job 空转返回 0 差异——P2 自助支付
    接入后由回调写入 payments，本任务自动开始出数。
    """
    paid_no_order = (
        db.query(sa.func.count(Payment.id))
        .join(Order, Payment.order_id == Order.id)
        .filter(Payment.status == "paid", Order.status != "granted")
        .scalar() or 0
    )
    if paid_no_order > 0:
        alert_svc.trigger_if_needed(
            db, rule_key="alert.reconcile_diff", level=NoticeLevel.CRITICAL,
            title=f"对账差异：{paid_no_order} 笔已支付订单未核销",
            content="payments.paid 但 orders 未 granted",
            metric={"diff_count": paid_no_order},
        )
    return {"diff_count": int(paid_no_order)}


@job_svc.register_inline("daily_report")
def daily_report(db) -> dict:
    """每日业务自查报表（04 §6，08:00）：复用 metrics_svc 单一实现落 JSON。"""
    now = dt.datetime.now(dt.UTC)
    day_start = (now - dt.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    day_end = day_start + dt.timedelta(days=1)
    report = {"date": day_start.date().isoformat(),
              **metrics_svc.daily_stats(db, day_start, day_end)}
    out_dir = os.environ.get("FJ_REPORT_DIR",
                             os.path.join(get_settings().upload_dir, "reports", "daily"))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{report['date']}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return {"saved": out_path, "tasks_total": report.get("tasks_total")}


# ── 调度 tick（runner 主循环调用）────────────────────────────────────────────


def tick() -> int:
    """扫描到期 sys_job 并执行。返回本轮执行数。异常吞掉不影响主任务循环。"""
    global _last_tick
    import time as _time

    now_mono = _time.monotonic()
    if now_mono - _last_tick < _TICK_INTERVAL:
        return 0
    _last_tick = now_mono
    ran = 0
    try:
        now = dt.datetime.now(dt.UTC)
        with SessionLocal() as db:
            for job in job_svc.due_jobs(db, now):
                if not job_svc.claim(db, job.id, job.cron_expr):
                    continue  # 并发被其他 worker 抢走
                ran += 1
                if job.job_key in job_svc.QUEUE_JOBS:
                    _enqueue_queue_job(db, job.job_key)
                    job_svc.write_log(db, job_key=job.job_key, job_id=job.id,
                                      status="ok", cost_ms=0,
                                      result={"enqueued": True}, error=None)
                else:
                    result = job_svc.run_inline(db, job)
                    if result.get("error"):
                        log.warning("job %s failed: %s", job.job_key, result["error"])
                    else:
                        log.info("job %s done: %s", job.job_key, result)
    except Exception:
        log.exception("sys_job tick failed")
    return ran


def _enqueue_queue_job(db, job_key: str) -> None:
    """queue 型 job → tasks 队列（唯一内置：purge，幂等由 enqueue 侧保证）。"""
    exists = (
        db.query(Task.id)
        .filter(Task.type == job_key, Task.status.in_(["pending", "running"]))
        .first()
    )
    if exists:
        return
    db.add(Task(type=job_key, status="pending"))
    db.commit()
