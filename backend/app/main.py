from pathlib import Path
import logging

import stripe
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import Base, engine
from .routes import admin, payments, stickers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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
    # Ensure database directory exists
    db_path = Path("data")
    db_path.mkdir(parents=True, exist_ok=True)

    # Create database tables with proper error handling
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logging.info("Database tables created successfully")
    except Exception as e:
        logging.error(f"Failed to create database tables: {e}")
        # Try to create the database file if it doesn't exist
        db_file = db_path / "stickers.db"
        if not db_file.exists():
            db_file.touch()
            logging.info(f"Created database file: {db_file}")
            # Retry table creation
            try:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                logging.info("Database tables created successfully on retry")
            except Exception as retry_error:
                logging.error(f"Failed to create database tables on retry: {retry_error}")
                raise
        else:
            raise

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
