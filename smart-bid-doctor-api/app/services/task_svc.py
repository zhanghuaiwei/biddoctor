import datetime as dt

from sqlalchemy.orm import Session

from app.core.enums import ParseStatus, TaskStatus, TaskType
from app.models import Task

# 任务链路（02 §8）：parse → extract → embed → checklist（招标文档侧，业务接入后级联）
# compare 独立触发。当前骨架仅创建任务，handler 为占位。


def create(db: Session, *, type_: str, project_id: int | None = None,
           document_id: int | None = None, comparison_id: int | None = None) -> Task:
    """创建任务（flush 不 commit），与调用方业务同事务提交"""
    t = Task(type=type_, project_id=project_id, document_id=document_id,
             comparison_id=comparison_id, status=TaskStatus.PENDING,
             run_after=dt.datetime.now(dt.UTC))
    db.add(t)
    db.flush()
    return t


def display_progress(task: Task | None, parse_status: str) -> int:
    """文档解析进度展示值：有任务用任务进度；无在途任务时按终态推导（done=100，其余 0）。

    状态机知识收敛在 service 层，api 不重复推导。
    """
    if task is not None:
        return int(task.progress)
    return 100 if parse_status == ParseStatus.DONE else 0


def get_owned(db: Session, task_id: int, user_id: int) -> Task | None:
    from app.models import Project

    return (
        db.query(Task)
        .join(Project, Task.project_id == Project.id)
        .filter(Task.id == task_id, Project.user_id == user_id, Project.deleted_at.is_(None))
        .first()
    )


def latest_for_document(db: Session, document_id: int, type_: str = TaskType.PARSE) -> Task | None:
    return (
        db.query(Task)
        .filter(Task.document_id == document_id, Task.type == type_)
        .order_by(Task.id.desc())
        .first()
    )
