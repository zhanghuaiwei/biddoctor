"""法务文档版本化与签署（legal_documents / user_agreements，05 §8）。

三类文档（用户协议/隐私政策/免责声明）版本化管理：draft → effective → retired，
同类型仅一版 effective（新版本生效即退役旧版）；签署记录支撑 PIPL「告知-同意」留痕。
"""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.enums import LegalDocType, LegalStatus
from app.core.errors import ERROR_CODES, AppError
from app.models import LegalDocument, UserAgreement


def create(db: Session, *, doc_type: str, version: str, title: str, content: str,
           effective_at: dt.datetime) -> LegalDocument:
    if doc_type not in LegalDocType:
        raise AppError(ERROR_CODES["VALIDATION_ERROR"], "VALIDATION_ERROR", "未知的文档类型")
    dup = db.query(LegalDocument.id).filter(
        LegalDocument.doc_type == doc_type, LegalDocument.version == version
    ).first()
    if dup:
        raise AppError(409, "LEGAL_VERSION_CONFLICT", "该版本号已存在")
    row = LegalDocument(
        doc_type=doc_type, version=version, title=title, content=content,
        effective_at=effective_at, status=LegalStatus.DRAFT,
    )
    db.add(row)
    db.commit()
    return row


def list_all(db: Session, *, doc_type: str | None = None) -> list[LegalDocument]:
    q = db.query(LegalDocument)
    if doc_type:
        q = q.filter(LegalDocument.doc_type == doc_type)
    return q.order_by(LegalDocument.doc_type.asc(),
                      LegalDocument.effective_at.desc()).all()


def publish(db: Session, doc_id: int) -> LegalDocument:
    """生效：同类型旧 effective 版本退役（同事务，保证同类型至多一版生效）。"""
    row = _get(db, doc_id)
    if row.status == LegalStatus.EFFECTIVE:
        raise AppError(409, "LEGAL_STATE", "该版本已生效")
    if row.status == LegalStatus.RETIRED:
        raise AppError(409, "LEGAL_STATE", "已退役版本不可再生效")
    old = (
        db.query(LegalDocument)
        .filter(LegalDocument.doc_type == row.doc_type,
                LegalDocument.status == LegalStatus.EFFECTIVE,
                LegalDocument.id != row.id)
        .all()
    )
    for o in old:
        o.status = LegalStatus.RETIRED
    row.status = LegalStatus.EFFECTIVE
    row.effective_at = dt.datetime.now(dt.UTC)
    db.commit()
    return row


def retire(db: Session, doc_id: int) -> LegalDocument:
    row = _get(db, doc_id)
    if row.status != LegalStatus.EFFECTIVE:
        raise AppError(409, "LEGAL_STATE", "仅生效中版本可退役")
    row.status = LegalStatus.RETIRED
    db.commit()
    return row


def current_effective(db: Session, doc_type: str) -> LegalDocument | None:
    return (
        db.query(LegalDocument)
        .filter(LegalDocument.doc_type == doc_type,
                LegalDocument.status == LegalStatus.EFFECTIVE)
        .first()
    )


def current_all(db: Session) -> list[LegalDocument]:
    """站点/报告页展示：三类文档当前生效版（缺类型跳过）。"""
    return (
        db.query(LegalDocument)
        .filter(LegalDocument.status == LegalStatus.EFFECTIVE)
        .order_by(LegalDocument.doc_type.asc())
        .all()
    )


def sign(db: Session, *, user_id: int, doc_id: int, ip: str | None) -> UserAgreement:
    """签署落痕：文档必须 effective；重复签署幂等跳过（已签同版本直接返回）。"""
    doc = _get(db, doc_id)
    if doc.status != LegalStatus.EFFECTIVE:
        raise AppError(409, "LEGAL_STATE", "文档未生效，不可签署")
    exists = (
        db.query(UserAgreement.id)
        .filter(UserAgreement.user_id == user_id,
                UserAgreement.legal_doc_id == doc_id)
        .first()
    )
    if exists:
        return db.get(UserAgreement, exists[0])
    row = UserAgreement(user_id=user_id, legal_doc_id=doc_id, ip=ip)
    db.add(row)
    db.commit()
    return row


def signed_doc_ids(db: Session, user_id: int) -> set[int]:
    rows = db.execute(
        sa.select(UserAgreement.legal_doc_id).where(UserAgreement.user_id == user_id)
    ).all()
    return {r[0] for r in rows}


def pending_effective(db: Session, user_id: int) -> list[LegalDocument]:
    """已生效但该用户未签署的文档（登录后强制签署弹层的数据源）。"""
    signed = signed_doc_ids(db, user_id)
    rows = current_all(db)
    return [d for d in rows if d.id not in signed]


def list_signatures(db: Session, *, limit: int = 20, offset: int = 0) -> tuple[list[UserAgreement], int]:
    q = db.query(UserAgreement)
    total = q.count()
    return q.order_by(UserAgreement.id.desc()).offset(offset).limit(min(limit, 100)).all(), total


def _get(db: Session, doc_id: int) -> LegalDocument:
    row = db.get(LegalDocument, doc_id)
    if row is None:
        raise AppError(404, "LEGAL_NOT_FOUND", "法务文档不存在")
    return row
