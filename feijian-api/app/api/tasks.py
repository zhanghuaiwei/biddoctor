from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.models import User
from app.schemas.project import TaskOut
from app.services import task_svc

router = APIRouter(prefix="/tasks", tags=["tasks"])  # 02 §9.6：GET /tasks/{id}


@router.get("/{tid}", response_model=TaskOut)
def get_task(tid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_svc.get_owned(db, tid, user.id)
    if task is None:
        raise AppError(404, "TASK_NOT_FOUND", "任务不存在")
    return TaskOut.model_validate(task)
