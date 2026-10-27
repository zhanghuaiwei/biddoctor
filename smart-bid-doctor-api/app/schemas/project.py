"""项目 / 文件 / 任务契约（02 §9.2、§9.6）"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    DocumentRole,
    EmbeddingStatus,
    Industry,
    ParseStatus,
    ProjectStatus,
    TaskStatus,
    TaskType,
)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    industry: Industry = Industry.GENERAL


class ProjectOut(BaseModel):
    id: int
    # DB 中是 UUID 对象；用 UUID 类型接收、序列化时自动输出字符串
    uuid: UUID
    name: str
    industry: Industry
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime  # 列表按 updated_at 排序，前端需要用于展示/轮询判断

    model_config = ConfigDict(from_attributes=True)


class DocumentOut(BaseModel):
    id: int
    role: DocumentRole
    orig_name: str
    sha256: str
    size_bytes: int
    total_pages: int | None
    parse_status: ParseStatus
    embedding_status: EmbeddingStatus
    parse_warnings: list[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListOut(BaseModel):
    items: list[DocumentOut]


class ProjectPage(BaseModel):
    items: list[ProjectOut]
    total: int


class UploadOut(BaseModel):
    """POST /projects/{id}/documents 响应（02 §9.2）"""

    document_id: int
    task_id: int | None
    dup: bool


class DocumentStatusOut(BaseModel):
    parse_status: ParseStatus
    progress: int
    stage: str | None
    warnings: list[str]
    # 扫描页占比是比例不是金额，schema 允许 float（JSON number，前端图形直接可用）
    is_scanned_ratio: float | None
    task_id: int | None


class TaskOut(BaseModel):
    id: int
    type: TaskType
    status: TaskStatus
    stage: str | None
    progress: int
    attempt: int
    error_code: str | None
    error_msg: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
