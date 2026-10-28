"""checklist handler（M1/D）：清单报告生成闭环（快照 → 渲染 → 落库 → 阅后即焚）。"""

import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.models import Project, Task
from app.services import audit_svc, check_svc
from app.worker.handlers.base import stub_done

log = logging.getLogger("worker.checklist")


# 编排职责（报告渲染方案见 app/engine/report/__init__.py 模块 docstring）：
#   1. 汇总 check_items → report_data 快照 → Jinja2 渲染 HTML → 落盘 → reports 落库；
#   2. project.status=report_ready（对照链不经此 handler）；
#   3. 阅后即焚：报告落库同事务软删原件（物理回收走 purge，03 §5）。
def run(task: dict, db: Session) -> None:
    project = db.get(Project, task["project_id"]) if task.get("project_id") else None
    if project is None:
        stub_done(db, task["id"], stage="report:project-missing")
        return
    try:
        rep = check_svc.generate_checklist_report(db, project)
    except Exception as exc:  # 确定性失败（缺招标文件等）显式置 failed，不静默重试
        log.exception("checklist report failed: project=%s", project.id)
        t = db.get(Task, task["id"])
        if t is not None:
            t.status = TaskStatus.FAILED
            t.error_code = getattr(exc, "code", "HANDLER_CRASH")
            t.error_msg = str(exc)[:500]
            t.finished_at = dt.datetime.now(dt.UTC)
            db.commit()
        return
    audit_svc.log(
        db, None, audit_svc.AuditAction.REPORT_GENERATED, target=f"report:{rep.id}",
        detail={"project_id": project.id, "kind": "checklist",
                "items": rep.report_data.get("stats", {}).get("total", 0)},
    )
    stub_done(db, task["id"], stage=f"report:done:{rep.id}")
