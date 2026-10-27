"""parse 桩：真实实现见 02 §2（PyMuPDF/pdfplumber/PaddleOCR 3.x）——M1 接入。
骨架版将文档标记为 need_review 并附提示，保持链路可观测。"""

from sqlalchemy.orm import Session

from app.core.enums import ParseStatus
from app.models import Document
from app.worker.handlers.base import stub_done


def run(task: dict, db: Session) -> None:
    doc = db.get(Document, task["document_id"])
    if doc is not None and doc.parse_status != ParseStatus.DONE:
        doc.parse_status = ParseStatus.NEED_REVIEW
        doc.parse_warnings = list(doc.parse_warnings or []) + [
            "骨架版：解析引擎未接入，解析结果不可用（M1 实现，见 02-详细设计 §2）"
        ]
        db.commit()
    stub_done(db, task["id"], stage="stub:parse")
