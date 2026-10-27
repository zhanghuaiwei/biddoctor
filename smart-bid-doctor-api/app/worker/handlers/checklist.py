"""checklist 桩：清单报告生成（M05/M07）见 02 §6——M1 接入。"""

from sqlalchemy.orm import Session

from app.worker.handlers.base import stub_done


def run(task: dict, db: Session) -> None:
    stub_done(db, task["id"], stage="stub:checklist")
