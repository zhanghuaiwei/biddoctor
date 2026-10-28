"""parse handler（M1/B）：解析引擎编排 → doc_blocks 落库 → 文档状态机 → 任务链续接。"""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.enums import EmbeddingStatus, ParseStatus
from app.core.errors import AppError
from app.engine import parser
from app.models import DocBlock, Document, Task
from app.worker.handlers.base import stub_done

_BATCH = 500


def run(task: dict, db: Session) -> None:
    """1) running+进度 → 2) 引擎解析 → 3) 分批落 doc_blocks → 4) done/need_review
    → 5) 入队 extract（抽取/对照为 LLM 范畴，extract 保持桩链路）。"""
    doc = db.get(Document, task["document_id"])
    if doc is None:
        stub_done(db, task["id"], stage="parse:doc-missing")
        return
    doc.parse_status = ParseStatus.RUNNING
    doc.parse_warnings = []
    _touch_task(db, task["id"], progress=2, stage="parse:open")
    db.commit()

    try:
        blocks, stats = parser.parse_pdf(doc.stored_path)
    except AppError as exc:
        # 确定性失败（加密/损坏）显式 _fail，不走 runner 重试（02 §8）
        doc.parse_status = ParseStatus.FAILED
        doc.parse_warnings = [exc.message]
        db.commit()
        t = db.get(Task, task["id"])
        if t is not None:
            t.status = "failed"
            t.error_code = exc.code
            t.error_msg = exc.message
            t.finished_at = dt.datetime.now(dt.UTC)
            db.commit()
        return

    # 分批 INSERT（~500 行/批，随批次推进任务进度 10→90）
    total = len(blocks)
    for i in range(0, total, _BATCH):
        chunk = blocks[i:i + _BATCH]
        db.execute(
            sa.insert(DocBlock),
            [
                {
                    "document_id": doc.id, "page": b.page, "seq": b.seq,
                    "type": b.type, "text": b.text, "section": b.section,
                }
                for b in chunk
            ],
        )
        _touch_task(db, task["id"],
                    progress=min(90, 10 + int(80 * (i + len(chunk)) / max(total, 1))),
                    stage=f"parse:page_{chunk[-1].page}")
        db.commit()

    scanned_ratio = stats.get("is_scanned_ratio") or 0
    doc.total_pages = stats.get("total_pages")
    doc.is_scanned_ratio = scanned_ratio
    if scanned_ratio >= 0.6:
        # 高扫描占比：无 OCR 兜底时文本不可靠，转人工复核（不静默当成功）
        doc.parse_status = ParseStatus.NEED_REVIEW
        doc.parse_warnings = [
            f"扫描页占比 {scanned_ratio:.0%}，文本层不可靠；OCR 兜底未启用（可选安装 PaddleOCR 后开启）"
        ]
    else:
        doc.parse_status = ParseStatus.DONE
        if scanned_ratio > 0:
            doc.parse_warnings = [
                f"含扫描页 {stats.get('scanned_pages')} 页（占比 {scanned_ratio:.0%}），对应页文本可能缺失"
            ]
    doc.embedding_status = EmbeddingStatus.PENDING
    _touch_task(db, task["id"], progress=95, stage="parse:chain")
    db.commit()

    # 任务链续接（02 §8）：extract 为 LLM 范畴（M1 接入前保持桩），由其级联 embed/checklist
    db.add(Task(type="extract", project_id=doc.project_id, document_id=doc.id))
    db.commit()
    stub_done(db, task["id"], stage=f"parse:done:{total}b")


def _touch_task(db: Session, task_id: int, *, progress: int, stage: str) -> None:
    t = db.get(Task, task_id)
    if t is not None:
        t.progress = max(t.progress or 0, progress)
        t.stage = stage
        t.heartbeat_at = dt.datetime.now(dt.UTC)
