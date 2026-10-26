"""handler 公共小工具：桩式完成/失败（业务接入后替换为真实状态推进）"""

import datetime as dt

from sqlalchemy.orm import Session

from app.models import Task


def stub_done(db: Session, task_id: int, stage: str = "stub") -> None:
    t = db.get(Task, task_id)
    if t is None:
        return
    t.status = "succeeded"
    t.stage = stage
    t.progress = 100
    t.finished_at = dt.datetime.now(dt.UTC)
    db.commit()
