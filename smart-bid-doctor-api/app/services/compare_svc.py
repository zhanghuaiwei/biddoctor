"""对照检查编排（02 §9.4）：校验双文件 → 扣配额 → 建 comparison → 建任务，单一事务提交。"""

from sqlalchemy.orm import Session

from app.core.enums import ComparisonStatus, DocumentRole, ParseStatus, ProjectStatus
from app.core.errors import AppError
from app.models import Comparison, Document, Project, User
from app.services import quota_svc, task_svc


def _project_documents(db: Session, project: Project) -> dict[str, Document]:
    docs = {
        d.role: d
        for d in db.query(Document)
        .filter(
            Document.project_id == project.id,
            Document.deleted_at.is_(None),
            Document.role.in_([DocumentRole.TENDER, DocumentRole.BID]),
        )
        .all()
    }
    return docs


def start_compare(db: Session, user: User, project: Project) -> tuple[Comparison, int]:
    # 校验顺序：先文档齐备/就绪（400），再原子扣配额（402 引导付费）——
    # 文档缺失时不做无谓的扣减+回滚写放大；扣减 UPDATE 未命中无副作用，无需 rollback
    docs = _project_documents(db, project)
    if DocumentRole.TENDER not in docs or DocumentRole.BID not in docs:
        raise AppError(400, "DOC_MISSING", "需先上传招标文件与投标文件各一份")
    if any(d.parse_status != ParseStatus.DONE for d in (docs["tender"], docs["bid"])):
        raise AppError(400, "DOC_NOT_READY", "文档解析未完成，请稍候再试")

    if quota_svc.consume_compare(db, user.id) is None:
        raise AppError(402, "QUOTA_EXCEEDED", "对照检查次数不足，请购买次数包")

    cmp_ = Comparison(
        project_id=project.id,
        tender_doc_id=docs["tender"].id,
        bid_doc_id=docs["bid"].id,
        status=ComparisonStatus.PENDING,
        stats={},
    )
    db.add(cmp_)
    db.flush()
    task = task_svc.create(db, type_="compare", project_id=project.id, comparison_id=cmp_.id)
    project.status = ProjectStatus.COMPARING
    db.commit()
    return cmp_, task.id


def latest(db: Session, project: Project) -> Comparison:
    cmp_ = (
        db.query(Comparison)
        .filter(Comparison.project_id == project.id)
        .order_by(Comparison.id.desc())
        .first()
    )
    if cmp_ is None:
        raise AppError(404, "COMPARISON_NOT_FOUND", "尚无对照记录")
    return cmp_
