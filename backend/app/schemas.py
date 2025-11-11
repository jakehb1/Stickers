from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class StickerBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    price_cents: int = Field(..., gt=0)
    currency: str = Field(default="usd", max_length=8)
    image_url: Optional[str] = None
    active: bool = True


class StickerCreate(StickerBase):
    pass


class StickerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    price_cents: Optional[int] = Field(default=None, gt=0)
    currency: Optional[str] = Field(default=None, max_length=8)
    active: Optional[bool] = None


class Sticker(StickerBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PurchaseCreate(BaseModel):
    sticker_id: int
    telegram_user_id: str
    email: Optional[str] = None


class Purchase(BaseModel):
    id: int
    sticker_id: int
    telegram_user_id: str
    stripe_session_id: str
    email: Optional[str]
    fulfilled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: int
