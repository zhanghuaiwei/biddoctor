"""purge 数据生命周期任务（03 §5 合规重点，非业务引擎）：

- 上传原件 PDF：默认留存 30 天（projects.retain_until）→ 到期删文件 + documents 软删
- 软删 documents 超 180 天 → 硬删（doc_blocks 经 FK ON DELETE CASCADE 级联）
- llm_calls / audit_logs / tasks：365 天物理 DELETE（量小，分区外简单删除）
- 所有删除动作写 audit_logs（action='data_purge'）

「阅后即焚」（报告生成即删原件）属于业务流程触发，不在本任务范围（M1 报告链路接入时实现）。
"""

import datetime as dt
import logging
import os

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditLog, Document, LlmCall, Project, Task
from app.services import audit_svc
from app.services.storage import LocalStorage
from app.worker.handlers.base import stub_done

log = logging.getLogger("worker.purge")

REPORT_RETENTION_DAYS = 180  # 软删后到硬删的观察期（03 §5：reports 等 180 天）
OPS_RETENTION_DAYS = 365  # llm_calls / audit_logs / tasks


def _delete_files(db: Session, docs: list[Document], storage: LocalStorage) -> int:
    """删除文档原件；sha256 寻址可能被其他在册文档复用（去重），仅删无引用的文件。"""
    removed = 0
    for d in docs:
        still_referenced = (
            db.query(sa.func.count(Document.id))
            .filter(
                Document.sha256 == d.sha256,
                Document.id != d.id,
                Document.deleted_at.is_(None),
            )
            .scalar()
            or 0
        )
        if still_referenced == 0 and d.stored_path and os.path.exists(d.stored_path):
            try:
                os.unlink(d.stored_path)
                removed += 1
            except OSError:
                log.exception("failed to unlink %s", d.stored_path)
    return removed


def run(task: dict, db: Session) -> None:
    s = get_settings()
    now = dt.datetime.now(dt.UTC)
    storage = LocalStorage(s.upload_dir)
    stats: dict[str, int] = {}

    # 1) retain_until 过期的在册项目：软删其未删 documents + 删无引用的原件
    expired_projects = (
        db.query(Project)
        .filter(Project.retain_until.is_not(None), Project.retain_until < now)
        .all()
    )
    if expired_projects:
        pids = [p.id for p in expired_projects]
        docs = (
            db.query(Document)
            .filter(
                Document.project_id.in_(pids),
                Document.deleted_at.is_(None),
            )
            .all()
        )
        stats["files_removed"] = _delete_files(db, docs, storage)
        for d in docs:
            d.deleted_at = now
        stats["documents_soft_deleted"] = len(docs)

    # 2) 软删超 180 天的 documents：硬删（doc_blocks 级联；文件此前已删）
    old_soft_deleted = (
        db.query(Document)
        .filter(
            Document.deleted_at.is_not(None),
            Document.deleted_at < now - dt.timedelta(days=REPORT_RETENTION_DAYS),
        )
        .all()
    )
    if old_soft_deleted:
        # 文件级兜底：正常流程第 1 步已删，这里仅清残留（同 sha 引用检查）
        stats["files_removed"] += _delete_files(db, old_soft_deleted, storage)
        stats["documents_hard_deleted"] = (
            db.query(Document)
            .filter(
                Document.deleted_at.is_not(None),
                Document.deleted_at < now - dt.timedelta(days=REPORT_RETENTION_DAYS),
            )
            .delete(synchronize_session=False)
        )

    # 3) 运维表 365 天物理删除（llm_calls / audit_logs / tasks 均按 created_at）
    for model, key in ((LlmCall, "llm_calls"), (Task, "tasks"), (AuditLog, "audit_logs")):
        cutoff = now - dt.timedelta(days=OPS_RETENTION_DAYS)
        stats[key] = (
            db.query(model).filter(model.created_at < cutoff).delete(synchronize_session=False)
        )

    db.commit()
    audit_svc.log(db, None, audit_svc.AuditAction.DATA_PURGE, target=f"task:{task['id']}",
                  detail=stats)
    log.info("purge done: %s", stats)
    stub_done(db, task["id"], stage="purge:done")
