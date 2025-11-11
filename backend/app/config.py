from functools import lru_cache
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./stickers.db"
    secret_key: str = "change-me"
    admin_password_hash: str = ""
    access_token_expire_minutes: int = 60 * 24
    stripe_secret_key: str = ""
    stripe_price_currency: str = "usd"
    stripe_success_url: str = "https://t.me"
    stripe_cancel_url: str = "https://t.me"
    stripe_webhook_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


class PublicConfig(BaseModel):
    stripe_publishable_key: str | None = None
    currency: str
