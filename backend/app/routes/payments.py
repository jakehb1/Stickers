from __future__ import annotations

import secrets
from datetime import datetime, timedelta

import httpx
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import PublicConfig, TonPublicConfig, get_settings
from ..database import get_session
from ..models import Purchase, Sticker, TonInvoice
from ..schemas import (
    PurchaseCreate,
    TonConfirmationRequest,
    TonInvoice as TonInvoiceSchema,
    TonInvoiceCreate,
    TonInvoiceResponse,
)

router = APIRouter(prefix="/payments", tags=["payments"])


def configure_stripe():
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Stripe not configured")
    stripe.api_key = settings.stripe_secret_key
    return settings


@router.get("/config", response_model=PublicConfig)
async def public_config():
    settings = get_settings()
    publishable_key = None
    if settings.stripe_secret_key.startswith("sk_"):
        publishable_key = settings.stripe_secret_key.replace("sk_", "pk_", 1)
    return PublicConfig(stripe_publishable_key=publishable_key, currency=settings.stripe_price_currency)


@router.get("/ton/config", response_model=TonPublicConfig)
async def ton_public_config():
    settings = ensure_ton_config()
    return TonPublicConfig(wallet_address=settings.ton_payment_wallet, invoice_ttl_seconds=settings.ton_invoice_ttl_seconds)


@router.post("/checkout")
async def create_checkout_session(
    payload: PurchaseCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    settings = configure_stripe()
    sticker = await session.get(Sticker, payload.sticker_id)
    if not sticker or not sticker.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sticker not found")

    image_urls = []
    if sticker.image_url:
        image_urls.append(request.url_for("static", path=sticker.image_url.lstrip("/")))

    purchase_currency = (sticker.currency or settings.stripe_price_currency).lower()

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": purchase_currency,
                    "product_data": {
                        "name": sticker.name,
                        "description": sticker.description or "",
                        "images": image_urls,
                    },
                    "unit_amount": sticker.price_cents,
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=settings.stripe_success_url,
        cancel_url=settings.stripe_cancel_url,
        metadata={
            "sticker_id": str(sticker.id),
            "telegram_user_id": payload.telegram_user_id,
            "email": payload.email or "",
        },
    )

    purchase = Purchase(
        sticker_id=sticker.id,
        telegram_user_id=payload.telegram_user_id,
        stripe_session_id=checkout_session["id"],
        payment_provider="stripe",
        email=payload.email,
        amount_paid=sticker.price_cents,
        currency=purchase_currency,
    )
    session.add(purchase)
    await session.commit()

    return {"checkout_url": checkout_session["url"], "session_id": checkout_session["id"]}


@router.post("/webhook")
async def stripe_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    endpoint_secret = request.app.state.stripe_webhook_secret

    if not endpoint_secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook not configured")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature") from exc

    if event["type"] == "checkout.session.completed":
        await handle_checkout_completed(event["data"]["object"], session)

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "received"})


async def handle_checkout_completed(data: dict, session: AsyncSession):
    session_id = data.get("id")
    if not session_id:
        return
    query = select(Purchase).where(Purchase.stripe_session_id == session_id)
    result = await session.execute(query)
    purchase = result.scalars().first()
    if not purchase:
        return
    purchase.fulfilled = True
    await session.commit()


@router.post("/ton/invoice", response_model=TonInvoiceResponse)
async def create_ton_invoice(
    payload: TonInvoiceCreate,
    session: AsyncSession = Depends(get_session),
):
    settings = ensure_ton_config()
    sticker = await session.get(Sticker, payload.sticker_id)
    if not sticker or not sticker.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sticker not found")

    if (sticker.currency or "").lower() != "ton":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sticker must be priced in TON minor units",
        )

    expires_at = datetime.utcnow() + timedelta(seconds=settings.ton_invoice_ttl_seconds)
    comment = await generate_unique_comment(session)

    invoice = TonInvoice(
        sticker_id=sticker.id,
        telegram_user_id=payload.telegram_user_id,
        email=payload.email,
        wallet_address=settings.ton_payment_wallet,
        amount_nanoton=sticker.price_cents,
        comment=comment,
        expires_at=expires_at,
    )
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)

    return TonInvoiceResponse(
        invoice_id=invoice.id,
        wallet_address=invoice.wallet_address,
        amount_nanoton=invoice.amount_nanoton,
        currency=(sticker.currency or "ton").lower(),
        comment=invoice.comment,
        expires_at=invoice.expires_at,
    )


@router.get("/ton/invoice/{invoice_id}", response_model=TonInvoiceSchema)
async def get_ton_invoice(invoice_id: int, session: AsyncSession = Depends(get_session)):
    invoice = await session.get(TonInvoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    await maybe_expire_invoice(invoice, session)
    await session.refresh(invoice)
    return invoice


@router.post("/ton/confirm", response_model=TonInvoiceSchema)
async def confirm_ton_payment(
    payload: TonConfirmationRequest,
    session: AsyncSession = Depends(get_session),
):
    settings = ensure_ton_config()
    invoice = await session.get(TonInvoice, payload.invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    await maybe_expire_invoice(invoice, session)
    if invoice.status == "expired":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invoice expired")

    if invoice.status == "confirmed":
        return invoice

    tx = await fetch_transaction_by_hash(settings, payload.transaction_hash)
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    validate_ton_transaction(invoice, tx, settings)

    invoice.status = "confirmed"
    invoice.transaction_hash = payload.transaction_hash
    invoice.confirmed_at = datetime.utcnow()
    invoice.confirmations = parse_confirmation_count(tx)

    existing_purchase = await session.execute(
        select(Purchase).where(Purchase.ton_invoice_id == invoice.id)
    )
    purchase = existing_purchase.scalars().first()
    if not purchase:
        purchase = Purchase(
            sticker_id=invoice.sticker_id,
            telegram_user_id=invoice.telegram_user_id,
            payment_provider="ton",
            ton_invoice_id=invoice.id,
            ton_transaction_hash=payload.transaction_hash,
            email=invoice.email,
            fulfilled=True,
            amount_paid=invoice.amount_nanoton,
            currency="ton",
        )
        session.add(purchase)
    else:
        purchase.fulfilled = True
        purchase.ton_transaction_hash = payload.transaction_hash
        purchase.payment_provider = "ton"
        purchase.amount_paid = invoice.amount_nanoton
        purchase.currency = "ton"

    await session.commit()
    await session.refresh(invoice)
    return invoice


def ensure_ton_config():
    settings = get_settings()
    if not settings.ton_payment_wallet:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TON payments are not configured",
        )
    return settings


async def generate_unique_comment(session: AsyncSession, attempts: int = 5) -> str:
    for _ in range(attempts):
        candidate = secrets.token_hex(4)
        existing = await session.execute(select(TonInvoice).where(TonInvoice.comment == candidate))
        if not existing.scalars().first():
            return candidate
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to allocate invoice comment")


async def maybe_expire_invoice(invoice: TonInvoice, session: AsyncSession):
    if invoice.status != "pending":
        return
    if invoice.expires_at <= datetime.utcnow():
        invoice.status = "expired"
        await session.commit()
        await session.refresh(invoice)


async def fetch_transaction_by_hash(settings, tx_hash: str):
    base_url = settings.ton_api_base_url.rstrip("/")
    url = f"{base_url}/blockchain/accounts/{settings.ton_payment_wallet}/transactions"
    headers = {}
    if settings.ton_api_key:
        headers["Authorization"] = f"Bearer {settings.ton_api_key}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params={"limit": 50}, headers=headers)
            if response.status_code >= 500:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="TON API unavailable")
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="TON API error") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to contact TON API") from exc

    for tx in data.get("transactions", []):
        hash_value = tx.get("hash") or ""
        if hash_value.lower() == tx_hash.lower():
            return tx
    return None


def validate_ton_transaction(invoice: TonInvoice, transaction: dict, settings) -> None:
    in_msg = transaction.get("in_msg") or {}
    destination = (in_msg.get("destination") or "").lower()
    if destination and destination != settings.ton_payment_wallet.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transaction not sent to configured wallet")

    comment = extract_transaction_comment(in_msg)
    if comment.strip() != invoice.comment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment mismatch")

    value_raw = in_msg.get("value") or 0
    if isinstance(value_raw, str):
        try:
            amount = int(value_raw)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TON value") from exc
    else:
        amount = int(value_raw)

    if amount < invoice.amount_nanoton:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient TON amount")

    confirmations = parse_confirmation_count(transaction)
    if confirmations < settings.ton_min_confirmations:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough confirmations")


def extract_transaction_comment(in_msg: dict) -> str:
    decoded = in_msg.get("decoded_body") or {}
    if isinstance(decoded, dict):
        comment = decoded.get("comment")
        if comment:
            return str(comment)

    msg_data = in_msg.get("msg_data") or {}
    if isinstance(msg_data, dict):
        text = msg_data.get("text") or msg_data.get("body") or msg_data.get("comment")
        if text:
            return str(text)

    return ""


def parse_confirmation_count(transaction: dict) -> int:
    raw_value = transaction.get("confirmation") or transaction.get("confirmations") or 0
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return 0
