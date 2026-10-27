"""配额 / 订单契约（02 §9.5）：金额一律 Decimal（Numeric 列，JSON 输出字符串避免精度丢失）"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.core.enums import OrderStatus


class OrderIn(BaseModel):
    sku: str  # 取值域由 Settings.sku_catalog 配置驱动（cmp_x5 | cmp_x20 | …）
    note: str | None = None


class OrderOut(BaseModel):
    order_no: str
    sku: str
    amount_cny: Decimal
    status: OrderStatus
    # 仅 POST /orders（创建）返回收款提示；列表查询为空串
    pay_hint: str = ""
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderPage(BaseModel):
    items: list[OrderOut]
    total: int


class QuotaPackOut(BaseModel):
    """次数包（quota_accounts 行）。type 为 SKU 代码（cmp_x5 等），取值域随配置。"""

    id: int
    type: str
    remain: int
    expires_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class QuotaOut(BaseModel):
    free_left: int
    packs: list[QuotaPackOut]


class GrantOut(BaseModel):
    order_no: str
    status: OrderStatus
