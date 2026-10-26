from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    industry: Literal["general", "medical"] = "general"


class ProjectOut(BaseModel):
    id: int
    # DB 中是 UUID 对象；用 UUID 类型接收、序列化时自动输出字符串
    uuid: UUID
    name: str
    industry: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: int
    role: str
    orig_name: str
    sha256: str
    size_bytes: int
    total_pages: int | None
    parse_status: str
    parse_warnings: list
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentStatusOut(BaseModel):
    parse_status: str
    progress: int
    stage: str | None
    warnings: list
    is_scanned_ratio: float | None
    task_id: int | None


class TaskOut(BaseModel):
    id: int
    type: str
    status: str
    stage: str | None
    progress: int
    error_code: str | None
    error_msg: str | None

    model_config = {"from_attributes": True}
