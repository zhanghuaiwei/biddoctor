from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class OrderIn(BaseModel):
    sku: Literal["cmp_x5", "cmp_x20"]
    note: str | None = None


class OrderOut(BaseModel):
    order_no: str
    sku: str
    amount_cny: float
    status: str
    pay_hint: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class QuotaOut(BaseModel):
    free_left: int
    packs: list[dict]


class GrantOut(BaseModel):
    order_no: str
    status: str
