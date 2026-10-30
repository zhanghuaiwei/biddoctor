"""embed handler（M2/E 前置）：块向量化编排 → pgvector 写回 → 文档状态机。

向量写入为对照检索前置（02 §5）；embedding 调用走 A 层桩——桩状态下任务
need_review、embedding_status 保持 pending（可重试语义，LLM 接入后重跑即补齐）。
空文档（无可向量化文本块）→ embedding_status=skipped 直接完成（合法终态）。
"""

import datetime as dt
import logging

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.core.enums import EmbeddingStatus, TaskStatus
from app.core.errors import AppError
from app.llm import zhipu
from app.llm.budget import CODE_BUDGET_EXCEEDED, BudgetExceeded, budget
from app.models import DocBlock, Document, Task
from app.worker.handlers.base import stub_done

log = logging.getLogger("worker.embed")

_BATCH = 16  # 每批向量条数（02 §5：分批调 embedding）


def run(task: dict, db: Session) -> None:
    doc = db.get(Document, task["document_id"])
    if doc is None:
        stub_done(db, task["id"], stage="embed:doc-missing")
        return

    blocks = (
        db.query(DocBlock)
        .filter(DocBlock.document_id == doc.id, DocBlock.embedding.is_(None))
        .order_by(DocBlock.page.asc(), DocBlock.seq.asc())
        .all()
    )
    pending = [b for b in blocks if (b.text or "").strip()]
    if not pending:
        # 无未向量化块：已有向量 → done；文档本身无文本块 → skipped
        has_vec = db.scalar(
            sa_text("SELECT EXISTS(SELECT 1 FROM doc_blocks "
                    "WHERE document_id = :d AND embedding IS NOT NULL)"),
            {"d": doc.id},
        )
        doc.embedding_status = EmbeddingStatus.DONE if has_vec else EmbeddingStatus.SKIPPED
        db.commit()
        stub_done(db, task["id"], stage="embed:noop")
        return

    provider = zhipu.ZhipuProvider()
    for i, chunk in enumerate([pending[j:j + _BATCH] for j in range(0, len(pending), _BATCH)]):
        try:
            vectors = provider.embed(
                [c.text for c in chunk],
                task_id=task["id"], project_id=doc.project_id,
            )
        except zhipu.CircuitOpenError as exc:
            _review(db, task["id"], zhipu.CODE_CIRCUIT_OPEN, str(exc))
            return
        except BudgetExceeded as exc:
            doc.embedding_status = EmbeddingStatus.FAILED
            db.commit()
            _fail(db, task["id"], CODE_BUDGET_EXCEEDED, str(exc))
            return
        except AppError as exc:
            if exc.code == "NOT_IMPLEMENTED":
                _review(db, task["id"], exc.code, exc.message)
                return
            raise  # 未知错误交 runner 退避重试
        for b, vec in zip(chunk, vectors, strict=False):
            b.embedding = vec
        _touch(db, task["id"],
               progress=10 + int(80 * (i + 1) / max(len(pending) // _BATCH + 1, 1)),
               stage=f"embed:batch_{i + 1}")
        db.commit()

    doc.embedding_status = EmbeddingStatus.DONE
    db.commit()
    budget.release(task["id"])
    stub_done(db, task["id"], stage=f"embed:done:{len(pending)}")


def _review(db: Session, task_id: int, code: str, msg: str) -> None:
    t = db.get(Task, task_id)
    if t is None:
        return
    t.status = TaskStatus.NEED_REVIEW
    t.error_code = code
    t.error_msg = msg[:500]
    t.finished_at = dt.datetime.now(dt.UTC)
    db.commit()


def _fail(db: Session, task_id: int, code: str, msg: str) -> None:
    t = db.get(Task, task_id)
    if t is None:
        return
    t.status = TaskStatus.FAILED
    t.error_code = code
    t.error_msg = msg[:500]
    t.finished_at = dt.datetime.now(dt.UTC)
    db.commit()
    budget.release(task_id)


def _touch(db: Session, task_id: int, *, progress: int, stage: str) -> None:
    t = db.get(Task, task_id)
    if t is not None:
        t.progress = max(t.progress or 0, progress)
        t.stage = stage
        t.heartbeat_at = dt.datetime.now(dt.UTC)
