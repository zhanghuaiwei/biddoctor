"""对照检查编排（02 §9.4）：扣配额 → 建 comparison → 建任务，单一事务提交。"""

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Comparison, Document, Project, User
from app.services import quota_svc, task_svc


def start_compare(db: Session, user: User, project: Project) -> tuple[Comparison, int]:
    # 校验顺序按 04 §2.2 时序：先配额（402 引导付费），再文档齐备/就绪
    quota_id = quota_svc.consume_compare(db, user.id)
    if quota_id is None:
        raise AppError(402, "QUOTA_EXCEEDED", "对照检查次数不足，请购买次数包")

    docs = {
        d.role: d
        for d in db.query(Document)
        .filter(Document.project_id == project.id, Document.deleted_at.is_(None))
        .all()
    }
    if "tender" not in docs or "bid" not in docs:
        db.rollback()  # 未消费成功，回滚扣减
        raise AppError(400, "DOC_MISSING", "需先上传招标文件与投标文件各一份")
    if any(d.parse_status != "done" for d in (docs["tender"], docs["bid"])):
        db.rollback()
        raise AppError(400, "DOC_NOT_READY", "文档解析未完成，请稍候再试")

    cmp_ = Comparison(
        project_id=project.id,
        tender_doc_id=docs["tender"].id,
        bid_doc_id=docs["bid"].id,
        status="pending",
        stats={},
    )
    db.add(cmp_)
    db.flush()
    task = task_svc.create(db, type_="compare", project_id=project.id, comparison_id=cmp_.id)
    project.status = "comparing"
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
