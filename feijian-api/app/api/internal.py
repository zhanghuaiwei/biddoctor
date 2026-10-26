import datetime as dt

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.models import LlmCall, Task
from app.services.storage import LocalStorage

router = APIRouter(tags=["internal"])


@router.get("/healthz")
def healthz(db: Session = Depends(get_db)):
    try:
        db.execute(sa.text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    s = get_settings()
    try:
        disk_free_mb = round(LocalStorage(s.upload_dir).disk_free_mb(), 1)
    except Exception:
        disk_free_mb = -1
    return {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "down", "disk_free_mb": disk_free_mb}


def _internal_auth(request: Request, db: Session) -> None:
    s = get_settings()
    token = request.headers.get("X-Internal-Token", "")
    if s.internal_token and token == s.internal_token:
        return
    # 未配置内部令牌时回退为管理员 Bearer（04 §6 告警脚本使用）
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        from app.core.security import decode_token
        from app.models import User as U

        try:
            payload = decode_token(auth.removeprefix("Bearer "))
            user = db.get(U, int(payload["sub"]))
            if user and user.role == "admin":
                return
        except Exception:
            pass
    raise AppError(401, "UNAUTHORIZED", "内部接口未授权")


@router.get("/internal/metrics")
def metrics(request: Request, db: Session = Depends(get_db)):
    _internal_auth(request, db)
    day_start = dt.datetime.now(dt.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    by_status = dict(
        db.query(Task.status, sa.func.count(Task.id))
        .filter(Task.created_at >= day_start)
        .group_by(Task.status)
        .all()
    )
    cost_today = (
        db.query(sa.func.coalesce(sa.func.sum(LlmCall.cost_cny), 0))
        .filter(LlmCall.created_at >= day_start)
        .scalar()
    )
    pending_backlog = (
        db.query(sa.func.count(Task.id)).filter(Task.status == "pending").scalar() or 0
    )
    return {
        "date": day_start.date().isoformat(),
        "tasks_today_by_status": by_status,
        "llm_cost_cny_today": float(cost_today),
        "pending_backlog": int(pending_backlog),
    }
