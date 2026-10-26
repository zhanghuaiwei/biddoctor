from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class OrderIn(BaseModel):
    sku: Literal["cmp_x5", "cmp_x20"]
    note: str | None = None


class OrderOut(BaseModel):
    order_no: str
    sku: str
    # 金额用 Decimal（Numeric 列），避免 float 精度问题
    amount_cny: Decimal
    status: str
    pay_hint: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderPage(BaseModel):
    items: list[OrderOut]


class QuotaOut(BaseModel):
    free_left: int
    packs: list[dict]


class GrantOut(BaseModel):
    order_no: str
    status: str
