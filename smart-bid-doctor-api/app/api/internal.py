"""健康检查与内部指标接口（04 §6）。

- GET /healthz：探活（DB 连通 + 磁盘余量），限流豁免，全站唯一允许直接 ORM 的例外；
- GET /internal/metrics：当日运营指标（任务分布 / LLM 成本 / 积压），供告警脚本与
  daily_report 使用。鉴权双通道：X-Internal-Token（hmac.compare_digest 常量时间比较）
  或管理员 Bearer（未配置内部令牌时回退，04 §6）。
"""

import datetime as dt
import decimal
import hmac

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.enums import UserRole
from app.core.errors import AppError
from app.schemas.internal import HealthOut, MetricsOut
from app.services import metrics_svc
from app.services.storage import LocalStorage

router = APIRouter(tags=["internal"])


@router.get("/healthz", response_model=HealthOut)
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
    return HealthOut(
        status="ok" if db_ok else "degraded",
        db="ok" if db_ok else "down",
        disk_free_mb=disk_free_mb,
    )


def _internal_auth(request: Request, db: Session) -> None:
    s = get_settings()
    token = request.headers.get("X-Internal-Token", "")
    if s.internal_token and hmac.compare_digest(token, s.internal_token):
        return
    # 未配置内部令牌时回退为管理员 Bearer（04 §6 告警脚本使用）
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        from app.core.security import decode_token
        from app.models import User as U

        try:
            payload = decode_token(auth.removeprefix("Bearer "))
            user = db.get(U, int(payload["sub"]))
            if user and user.role == UserRole.ADMIN:
                return
        except Exception:
            pass
    raise AppError(401, "UNAUTHORIZED", "内部接口未授权")


@router.get("/internal/metrics", response_model=MetricsOut)
def metrics(request: Request, db: Session = Depends(get_db)):
    _internal_auth(request, db)
    day_start = dt.datetime.now(dt.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    stats = metrics_svc.daily_stats(db, day_start, day_start + dt.timedelta(days=1))
    return MetricsOut(
        date=day_start.date().isoformat(),
        tasks_today_by_status=stats["tasks_by_status"],
        # 金额走 Decimal（经 str 中转，避免 float 二进制误差进账本口径）
        llm_cost_cny_today=decimal.Decimal(str(stats["llm_cost_cny"])),
        pending_backlog=stats["pending_backlog"],
    )
