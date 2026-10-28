"""运维监控聚合（05 §4.1 监控大盘）：任务 / LLM / 容量水位，即席聚合不建表。

磁盘统计按 FJ_UPLOAD_DIR 根目录下分类子目录（uploads/reports/attachments）汇总；
doc_blocks 行数为扩容触发观测指标（04 §4 扩容线 500 万行）。
"""

import datetime as dt
import os

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import DocBlock, Document, LlmCall, Task


def _dir_size_mb(path: str) -> float:
    if not os.path.isdir(path):
        return 0.0
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                continue
    return round(total / 1024 / 1024, 2)


def disk_usage(db: Session) -> dict:
    s = get_settings()
    root = s.upload_dir
    usage = {
        "root": root,
        "free_mb": None,
        "total_mb": None,
        "usage_ratio": None,
        "uploads_mb": 0.0,
        "reports_mb": 0.0,
        "attachments_mb": 0.0,
    }
    try:
        stat = os.statvfs(root)
        free = stat.f_bavail * stat.f_frsize
        total = stat.f_blocks * stat.f_frsize
        usage["free_mb"] = round(free / 1024 / 1024, 2)
        usage["total_mb"] = round(total / 1024 / 1024, 2)
        usage["usage_ratio"] = round(1 - free / total, 4) if total else None
    except OSError:
        pass
    if os.path.isdir(root):
        for name, key in (("uploads", "uploads_mb"), ("reports", "reports_mb"),
                          ("attachments", "attachments_mb")):
            usage[key] = _dir_size_mb(os.path.join(root, name))
        # 兼容 LocalStorage 直接以根目录为上传根（uploads 未分子目录）的布局
        if usage["uploads_mb"] == 0.0 and not os.path.isdir(os.path.join(root, "uploads")):
            usage["uploads_mb"] = _dir_size_mb(root)
    return usage


def task_overview(db: Session) -> dict:
    now = dt.datetime.now(dt.UTC)
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    by_status = dict(db.execute(
        sa.select(Task.status, func.count(Task.id)).group_by(Task.status)
    ).all())
    today_total = db.query(func.count(Task.id)).filter(
        Task.created_at >= today0, Task.type != "purge").scalar() or 0
    today_ok = db.query(func.count(Task.id)).filter(
        Task.created_at >= today0, Task.type != "purge",
        Task.status == "succeeded").scalar() or 0
    oldest_pending = db.query(Task.created_at).filter(
        Task.status == "pending").order_by(Task.created_at.asc()).first()
    backlog_min = (
        int((now - oldest_pending[0]).total_seconds() / 60) if oldest_pending else 0
    )
    return {
        "by_status": by_status,
        "pending": int(by_status.get("pending", 0)),
        "running": int(by_status.get("running", 0)),
        "need_review": int(by_status.get("need_review", 0)),
        "today_total": int(today_total),
        "today_success_rate": round(today_ok / today_total, 4) if today_total else None,
        "backlog_minutes": backlog_min,
    }


def llm_overview(db: Session) -> dict:
    """各模型调用量/成功率/时延/token 成本（M1 接入前空表全 0）。"""
    now = dt.datetime.now(dt.UTC)
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = db.execute(
        sa.select(
            LlmCall.model,
            func.count(LlmCall.id),
            func.sum(sa.case((LlmCall.error.is_(None), 1), else_=0)),
            func.avg(LlmCall.latency_ms),
            func.sum(LlmCall.prompt_tokens),
            func.sum(LlmCall.output_tokens),
            func.sum(LlmCall.cost_cny),
        ).group_by(LlmCall.model)
    ).all()
    models = [
        {
            "model": m, "calls": int(c), "success_rate": round(s / c, 4) if c else None,
            "avg_latency_ms": round(float(lat), 1) if lat is not None else None,
            "prompt_tokens": int(p or 0), "output_tokens": int(o or 0),
            "cost_cny": str(round(float(cost or 0), 4)),
        }
        for m, c, s, lat, p, o, cost in rows
    ]
    today_cost = db.query(func.sum(LlmCall.cost_cny)).filter(
        LlmCall.created_at >= today0).scalar() or 0
    today_calls = db.query(func.count(LlmCall.id)).filter(
        LlmCall.created_at >= today0).scalar() or 0
    return {"models": models, "today_calls": int(today_calls),
            "today_cost_cny": str(round(float(today_cost), 4))}


def capacity(db: Session) -> dict:
    doc_blocks = db.query(func.count(DocBlock.id)).scalar() or 0
    docs = db.query(func.count(Document.id)).filter(
        Document.deleted_at.is_(None)).scalar() or 0
    return {"doc_blocks_rows": int(doc_blocks), "documents": int(docs)}


def overview(db: Session) -> dict:
    return {
        "tasks": task_overview(db),
        "llm": llm_overview(db),
        "capacity": capacity(db),
    }


def task_list(db: Session, *, status: str | None = None, type_: str | None = None,
              limit: int = 20, offset: int = 0) -> tuple[list[Task], int]:
    q = db.query(Task)
    if status:
        q = q.filter(Task.status == status)
    if type_:
        q = q.filter(Task.type == type_)
    total = q.count()
    return q.order_by(Task.id.desc()).offset(offset).limit(min(limit, 100)).all(), total
