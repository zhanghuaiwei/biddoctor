"""行业包规则库（rule_sets / rule_items，P2，db DDL §17-18）。

版本状态机 draft → active → retired；同 (industry, law_version) 至多一版 active
（新版本激活即退役旧版）。条目注入 extractor 规则预筛（hint）与 comparator 规则
复核（must/veto）——M2 引擎接入时读取；管理端 CRUD 与版本管理先行。
"""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.enums import Industry, RuleSetStatus
from app.core.errors import ERROR_CODES, AppError
from app.models import RuleItem, RuleSet


def list_sets(db: Session, *, industry: str | None = None) -> list[RuleSet]:
    q = db.query(RuleSet)
    if industry:
        q = q.filter(RuleSet.industry == industry)
    return q.order_by(RuleSet.industry.asc(), RuleSet.law_version.asc(),
                      RuleSet.version.desc()).all()


def create_set(db: Session, *, industry: str, law_version: str, notes: str | None) -> RuleSet:
    if industry not in Industry:
        raise AppError(ERROR_CODES["VALIDATION_ERROR"], "VALIDATION_ERROR", "未知的行业")
    version = (
        db.query(sa.func.max(RuleSet.version))
        .filter(RuleSet.industry == industry, RuleSet.law_version == law_version)
        .scalar()
        or 0
    ) + 1
    row = RuleSet(
        industry=industry, law_version=law_version, version=version,
        status=RuleSetStatus.DRAFT, notes=notes,
    )
    db.add(row)
    db.commit()
    return row


def activate_set(db: Session, set_id: int) -> RuleSet:
    row = _get(db, set_id)
    if row.status == RuleSetStatus.ACTIVE:
        raise AppError(409, "RULESET_STATE", "该版本已激活")
    if row.status == RuleSetStatus.RETIRED:
        raise AppError(409, "RULESET_STATE", "已退役版本不可再激活")
    db.execute(
        sa.update(RuleSet)
        .where(RuleSet.industry == row.industry,
               RuleSet.law_version == row.law_version,
               RuleSet.status == RuleSetStatus.ACTIVE,
               RuleSet.id != row.id)
        .values(status=RuleSetStatus.RETIRED)
    )
    row.status = RuleSetStatus.ACTIVE
    row.effective_from = dt.datetime.now(dt.UTC)
    db.commit()
    return row


def retire_set(db: Session, set_id: int) -> RuleSet:
    row = _get(db, set_id)
    if row.status != RuleSetStatus.ACTIVE:
        raise AppError(409, "RULESET_STATE", "仅激活版本可退役")
    row.status = RuleSetStatus.RETIRED
    db.commit()
    return row


def list_items(db: Session, rule_set_id: int) -> list[RuleItem]:
    _get(db, rule_set_id)
    return (
        db.query(RuleItem)
        .filter(RuleItem.rule_set_id == rule_set_id)
        .order_by(RuleItem.category.asc(), RuleItem.id.asc())
        .all()
    )


def add_item(db: Session, rule_set_id: int, *, category: str, kind: str, pattern: str,
             action: str = "hint", weight: float = 1.0, description: str | None = None) -> RuleItem:
    _get(db, rule_set_id)
    row = RuleItem(
        rule_set_id=rule_set_id, category=category, kind=kind, pattern=pattern,
        action=action, weight=weight, description=description,
    )
    db.add(row)
    db.commit()
    return row


def delete_item(db: Session, item_id: int) -> None:
    row = db.get(RuleItem, item_id)
    if row is None:
        raise AppError(404, "RULESET_NOT_FOUND", "规则条目不存在")
    db.delete(row)
    db.commit()


def active_items(db: Session, industry: str) -> list[RuleItem]:
    """引擎接入点：指定行业当前 active 规则库的全部条目。"""
    return (
        db.query(RuleItem)
        .join(RuleSet, RuleItem.rule_set_id == RuleSet.id)
        .filter(RuleSet.industry == industry, RuleSet.status == RuleSetStatus.ACTIVE)
        .order_by(RuleItem.category.asc(), RuleItem.id.asc())
        .all()
    )


def _get(db: Session, set_id: int) -> RuleSet:
    row = db.get(RuleSet, set_id)
    if row is None:
        raise AppError(404, "RULESET_NOT_FOUND", "规则库不存在")
    return row
