from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Sticker(Base):
    __tablename__ = "stickers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="usd", nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sticker_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    telegram_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_provider: Mapped[str] = mapped_column(String(32), default="stripe", nullable=False)
    stripe_session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    ton_invoice_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    ton_transaction_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fulfilled: Mapped[bool] = mapped_column(Boolean, default=False)
    amount_paid: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="usd")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TonInvoice(Base):
    __tablename__ = "ton_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sticker_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    telegram_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    wallet_address: Mapped[str] = mapped_column(String(256), nullable=False)
    amount_nanoton: Mapped[int] = mapped_column(BigInteger, nullable=False)
    comment: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    transaction_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True)
    confirmations: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
