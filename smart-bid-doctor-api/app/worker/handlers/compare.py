"""compare 桩：双文件对照引擎（混合检索 + GLM 判定 + 规则复核）见 02 §4——M2 接入。
骨架版将 comparison 置为 need_review（次数已消耗的演示环境用，真实环境勿放开）。"""

from sqlalchemy.orm import Session

from app.core.enums import ComparisonStatus
from app.models import Comparison
from app.worker.handlers.base import stub_done


def run(task: dict, db: Session) -> None:
    if task.get("comparison_id"):
        cmp_ = db.get(Comparison, task["comparison_id"])
        if cmp_ is not None and cmp_.status == ComparisonStatus.PENDING:
            cmp_.status = ComparisonStatus.NEED_REVIEW
            cmp_.stats = {"stub": True}
            db.commit()
    stub_done(db, task["id"], stage="stub:compare")
