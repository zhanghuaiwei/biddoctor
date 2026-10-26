import datetime as dt

from sqlalchemy.orm import Session

from app.models import Task

# 任务链路（02 §8）：parse → extract → embed → checklist（招标文档侧，业务接入后级联）
# compare 独立触发。当前骨架仅创建任务，handler 为占位。


def create(db: Session, *, type_: str, project_id: int | None = None,
           document_id: int | None = None, comparison_id: int | None = None) -> Task:
    """创建任务（flush 不 commit），与调用方业务同事务提交"""
    t = Task(type=type_, project_id=project_id, document_id=document_id,
             comparison_id=comparison_id, status="pending",
             run_after=dt.datetime.now(dt.UTC))
    db.add(t)
    db.flush()
    return t


def get_owned(db: Session, task_id: int, user_id: int) -> Task | None:
    from app.models import Project

    return (
        db.query(Task)
        .join(Project, Task.project_id == Project.id)
        .filter(Task.id == task_id, Project.user_id == user_id, Project.deleted_at.is_(None))
        .first()
    )
