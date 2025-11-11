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
    payment_provider: str
    stripe_session_id: Optional[str]
    ton_invoice_id: Optional[int]
    ton_transaction_hash: Optional[str]
    email: Optional[str]
    fulfilled: bool
    amount_paid: int
    currency: str
    created_at: datetime

    class Config:
        from_attributes = True


class TonInvoiceCreate(BaseModel):
    sticker_id: int
    telegram_user_id: str
    email: Optional[str] = None


class TonInvoiceResponse(BaseModel):
    invoice_id: int
    wallet_address: str
    amount_nanoton: int
    currency: str
    comment: str
    expires_at: datetime


class TonInvoice(BaseModel):
    id: int
    sticker_id: int
    telegram_user_id: str
    email: Optional[str]
    wallet_address: str
    amount_nanoton: int
    comment: str
    status: str
    transaction_hash: Optional[str]
    confirmations: int
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    confirmed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TonConfirmationRequest(BaseModel):
    invoice_id: int
    transaction_hash: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: int
