"""extract 桩：条款抽取引擎（规则预筛 + GLM 结构化抽取 + 合并）见 02 §3——M1 接入。"""

from sqlalchemy.orm import Session

from app.worker.handlers.base import stub_done


def run(task: dict, db: Session) -> None:
    stub_done(db, task["id"], stage="stub:extract")
