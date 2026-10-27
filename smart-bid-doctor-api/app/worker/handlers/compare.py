"""compare 桩：双文件对照引擎（混合检索 + GLM 判定 + 规则复核）见 02 §4——M2 接入。
骨架版将 comparison 置为 need_review（次数已消耗的演示环境用，真实环境勿放开）。"""

from sqlalchemy.orm import Session

from app.core.enums import ComparisonStatus
from app.models import Comparison
from app.worker.handlers.base import stub_done


# TODO(M2) handler 编排职责（对照引擎方案见 app/engine/comparator/__init__.py TODO 块）：
#   1. 前置校验双文档块向量就绪 → comparison.status=running；
#   2. 逐条 check_item 混合检索 → GLM 判定（purpose=judge 记账）→ 规则复核 → findings 落库；
#   3. stats 汇总（红/黄/绿计数）→ status=done → 建对照报告任务（checklist handler 复用渲染）；
#   4. 失败语义：配额在对照发起时已扣，comparison 级失败不回滚次数，走 need_review 人工处理。
def run(task: dict, db: Session) -> None:
    if task.get("comparison_id"):
        cmp_ = db.get(Comparison, task["comparison_id"])
        if cmp_ is not None and cmp_.status == ComparisonStatus.PENDING:
            cmp_.status = ComparisonStatus.NEED_REVIEW
            cmp_.stats = {"stub": True}
            db.commit()
    stub_done(db, task["id"], stage="stub:compare")
