"""清单 / 对照 / 报告契约（02 §9.3、§9.4）"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.enums import CheckCategory, ComparisonStatus, ReportKind


class CheckItemOut(BaseModel):
    id: int
    code: str
    category: CheckCategory
    requirement: str
    raw_text: str
    ref_page: int
    is_mandatory: bool
    confidence: float  # 0-1 比例值非金额，float 便于前端直接渲染

    model_config = ConfigDict(from_attributes=True)


class CheckItemsPage(BaseModel):
    items: list[CheckItemOut]
    total: int
    stats: dict[str, int]  # category -> count


class ComparisonOut(BaseModel):
    id: int
    project_id: int
    tender_doc_id: int
    bid_doc_id: int
    status: ComparisonStatus
    stats: dict[str, Any]  # {"red":2,"yellow":5,"green":43}（M2 对照引擎写入）
    created_at: datetime
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class CompareStartedOut(BaseModel):
    """POST /projects/{id}/compare 响应（02 §9.4）"""

    comparison_id: int
    task_id: int


class ReportOut(BaseModel):
    id: int
    project_id: int
    kind: ReportKind
    report_data: dict[str, Any]  # 02 §6.2 报告结构
    disclaimer_ack: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportPage(BaseModel):
    items: list[ReportOut]
    total: int


class ChecklistStartedOut(BaseModel):
    """POST /projects/{id}/checklist-report 响应：任务 id（前端轮询终态后拉报告）。"""

    task_id: int


class FeedbackIn(BaseModel):
    """findings 质量回流（P2，05 §6.2）：用户认可/误报标记。"""

    feedback: str  # agree | disagree
    note: str | None = None


class FeedbackOut(BaseModel):
    id: int
    feedback: str | None
    feedback_note: str | None
    feedback_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
