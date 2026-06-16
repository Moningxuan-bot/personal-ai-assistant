import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

SPENDING_CATEGORIES = Literal["餐饮", "交通", "烟酒", "购物", "娱乐", "其他"]


class SpendingCreate(BaseModel):
    amount: float = Field(gt=0, le=99999999.99)
    category: SPENDING_CATEGORIES
    note: str | None = None
    conversation_id: uuid.UUID | None = None


class SpendingResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID | None
    amount: float
    category: str
    note: str | None
    reaction: str
    chat_reaction: str | None
    chat_delivered: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SpendingStats(BaseModel):
    month: str
    total: float
    by_category: dict[str, float]
    ajiu_comment: str
