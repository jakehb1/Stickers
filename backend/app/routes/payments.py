import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import PublicConfig, get_settings
from ..database import get_session
from ..models import Purchase, Sticker
from ..schemas import PurchaseCreate

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

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": sticker.currency or settings.stripe_price_currency,
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
        email=payload.email,
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
