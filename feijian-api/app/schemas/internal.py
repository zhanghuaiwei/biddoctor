"""运维/内部端点响应契约（02 §9.6）"""

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str  # ok | degraded
    db: str  # ok | down
    disk_free_mb: float


class MetricsOut(BaseModel):
    date: str
    tasks_today_by_status: dict[str, int]
    llm_cost_cny_today: float
    pending_backlog: int
