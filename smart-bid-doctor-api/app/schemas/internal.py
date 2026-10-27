"""运维/内部端点响应契约（02 §9.6）"""

from decimal import Decimal

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str  # ok | degraded
    db: str  # ok | down
    disk_free_mb: float  # 磁盘余量（MB），非金额可用 float


class MetricsOut(BaseModel):
    date: str
    tasks_today_by_status: dict[str, int]
    llm_cost_cny_today: Decimal  # 金额：Decimal 序列化为字符串，避免浮点误差
    pending_backlog: int
