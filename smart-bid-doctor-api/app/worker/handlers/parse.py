"""parse 桩：真实实现见 02 §2（PyMuPDF/pdfplumber/PaddleOCR 3.x）——M1 接入。
骨架版将文档标记为 need_review 并附提示，保持链路可观测。"""

from sqlalchemy.orm import Session

from app.core.enums import ParseStatus
from app.models import Document
from app.worker.handlers.base import stub_done


# TODO(M1/B1–B3) handler 编排职责（解析引擎方案见 app/engine/parser/__init__.py TODO 块）：
#   1. 取 document → parse_status=running，任务 progress 按页推进（有 page 粒度则回调更新）；
#   2. 调 engine.parser 解析 → doc_blocks 分批落库 → parse_status=done；
#   3. 加密/损坏 → PARSE_ENCRYPTED / PARSE_CORRUPT 显式 _fail（确定性失败不重试，B3）；
#   4. 成功后按任务链（02 §8）入队 extract 任务（extract→embed→checklist 级联由各 handler 续接）；
#   5. 可恢复异常 → raise 交 runner 统一退避重试（attempt ≤3），不在 handler 内吞异常。
def run(task: dict, db: Session) -> None:
    doc = db.get(Document, task["document_id"])
    if doc is not None and doc.parse_status != ParseStatus.DONE:
        doc.parse_status = ParseStatus.NEED_REVIEW
        doc.parse_warnings = list(doc.parse_warnings or []) + [
            "骨架版：解析引擎未接入，解析结果不可用（M1 实现，见 02-详细设计 §2）"
        ]
        db.commit()
    stub_done(db, task["id"], stage="stub:parse")
