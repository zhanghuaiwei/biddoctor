"""embed 桩：块向量化（智谱 embedding-3, dimensions=1024）见 02 §5——M1 接入。"""

from sqlalchemy.orm import Session

from app.worker.handlers.base import stub_done


def run(task: dict, db: Session) -> None:
    stub_done(db, task["id"], stage="stub:embed")
