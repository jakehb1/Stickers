from pathlib import Path

import stripe
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import Base, engine
from .routes import admin, payments, stickers

app = FastAPI(title="Sticker Shop")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.stripe_webhook_secret = settings.stripe_webhook_secret
    if settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key


static_path = Path(__file__).resolve().parents[1] / "static"
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

app.include_router(admin.router)
app.include_router(stickers.router)
app.include_router(payments.router)


@app.get("/")
async def root():
    return {"message": "Sticker store backend running"}
