"""checklist 桩：清单报告生成（M05/M07）见 02 §6——M1 接入。"""

from sqlalchemy.orm import Session

from app.worker.handlers.base import stub_done


# TODO(M1/D2–D3) handler 编排职责（报告渲染方案见 app/engine/report/__init__.py TODO 块）：
#   1. 汇总 check_items → report_data 快照 → Jinja2 渲染 HTML → Storage 落盘 → reports 落库；
#   2. project.status=report_ready（对照链不经此 handler）；
#   3. D3 阅后即焚：报告生成成功后删原件文件 + doc_blocks（03 §5，业务触发式 purge）。
def run(task: dict, db: Session) -> None:
    stub_done(db, task["id"], stage="stub:checklist")
