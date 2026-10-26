from datetime import datetime

from pydantic import BaseModel


class CheckItemOut(BaseModel):
    id: int
    code: str
    category: str
    requirement: str
    raw_text: str
    ref_page: int
    is_mandatory: bool
    confidence: float

    model_config = {"from_attributes": True}


class CheckItemsPage(BaseModel):
    items: list[CheckItemOut]
    total: int
    stats: dict


class ComparisonOut(BaseModel):
    id: int
    status: str
    stats: dict
    created_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class ReportOut(BaseModel):
    id: int
    project_id: int
    kind: str
    report_data: dict
    created_at: datetime

    model_config = {"from_attributes": True}
