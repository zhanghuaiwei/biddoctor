"""extract 桩：条款抽取引擎（规则预筛 + GLM 结构化抽取 + 合并）见 02 §3——M1 接入。"""

from sqlalchemy.orm import Session

from app.worker.handlers.base import stub_done


# TODO(M1/C1–C3) handler 编排职责（抽取引擎方案见 app/engine/extractor/__init__.py TODO 块）：
#   1. 校验 parse_status=done（否则 need_review / 显式失败）→ project.status=tender_parsing；
#   2. 调 engine.extractor：预筛 → GLM 抽取（llm_calls 记账）→ check_items 落库；
#   3. 抽取完成 → project.status=checklist_ready → 入队 embed 任务（对照前置）；
#   4. budget 超限（02 §7）→ 确定性失败 _fail（BUDGET_EXCEEDED，错误码同步注册表）。
def run(task: dict, db: Session) -> None:
    stub_done(db, task["id"], stage="stub:extract")
