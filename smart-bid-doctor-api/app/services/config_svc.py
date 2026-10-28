"""运行时参数（sys_config，05 §3.1）：改值即生效——进程内 TTL 缓存 + 失效主动清。

取值优先级：sys_config 行 > Settings 默认值。配额等 L4 语义参数读本表
（quota.free_monthly），管理端改值无需重启即生效；表未初始化时兜底 Settings。
"""

import datetime as dt
import json
import logging

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.enums import ConfigValueType
from app.core.errors import AppError
from app.models import SysConfig

_logger = logging.getLogger("app.config")

_TTL = dt.timedelta(seconds=60)
_cache: dict[str, tuple[str, dt.datetime]] = {}


def get_raw(db: Session, key: str) -> str | None:
    """读原始值（str）。带 TTL 缓存；DB 异常时静默回退 None（参数缺失不阻断业务）。"""
    hit = _cache.get(key)
    now = dt.datetime.now(dt.UTC)
    if hit and now - hit[1] < _TTL:
        return hit[0]
    try:
        value = db.execute(
            sa.select(SysConfig.value).where(SysConfig.config_key == key)
        ).scalar_one_or_none()
    except Exception:
        _logger.exception("sys_config read failed: key=%s", key)
        return None
    if value is not None:
        _cache[key] = (value, now)
    return value


def invalidate(key: str | None = None) -> None:
    """改值后失效缓存（全部清更安全——键数量少）。"""
    if key is None:
        _cache.clear()
    else:
        _cache.pop(key, None)


def get_int(db: Session, key: str, default: int) -> int:
    raw = get_raw(db, key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def get_float(db: Session, key: str, default: float) -> float:
    raw = get_raw(db, key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def get_bool(db: Session, key: str, default: bool) -> bool:
    raw = get_raw(db, key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def update(db: Session, *, key: str, value: str, admin_id: int) -> SysConfig:
    """改参数值：value_type 反序列化校验先行（坏值拒绝入库），失败回滚不半提交。"""
    row = db.query(SysConfig).filter(SysConfig.config_key == key).first()
    if row is None:
        raise AppError(404, "CONFIG_NOT_FOUND", "参数不存在")
    try:
        _coerce(row.value_type, value)
    except (ValueError, TypeError) as exc:
        raise AppError(400, "CONFIG_VALUE_INVALID", f"值不符合 {row.value_type} 类型要求") from exc
    row.value = value
    row.updated_by = admin_id
    row.updated_at = dt.datetime.now(dt.UTC)
    db.commit()
    invalidate(key)
    return row


def _coerce(value_type: str, raw: str):
    if value_type == ConfigValueType.INT:
        return int(raw)
    if value_type == ConfigValueType.BOOL:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if value_type == ConfigValueType.JSON:
        return json.loads(raw)
    return raw


def list_all(db: Session) -> list[SysConfig]:
    return db.query(SysConfig).order_by(SysConfig.config_key.asc()).all()
