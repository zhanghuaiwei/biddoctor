"""handler 公共小工具：桩式完成（业务接入后由各 handler 的真实状态推进替换）。

真实引擎接入后：parse/extract/embed/checklist/compare 均改为按业务更新
progress/stage 并置终态，本函数仅保留给 purge 等生命周期任务过渡使用；
M1 全部业务 handler 就绪后可删除本函数与各 stub 引用（F1 清理项）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.core.enums import TaskStatus
from app.models import Task


def stub_done(db: Session, task_id: int, stage: str = "stub") -> None:
    t = db.get(Task, task_id)
    if t is None:
        return
    t.status = TaskStatus.SUCCEEDED
    t.stage = stage
    t.progress = 100
    t.finished_at = dt.datetime.now(dt.UTC)
    db.commit()
