from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
    
from .config import get_settings
from .schemas import TokenPayload
import bcrypt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = HTTPBearer()

async def authenticate_admin(password: str) -> bool:
    settings = get_settings()
    if not settings.admin_password_hash:
        raise RuntimeError("ADMIN_PASSWORD_HASH is not set.")
    return verify_password(password, settings.admin_password_hash)

def verify_password(plain_password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed.encode("utf-8"))

def create_access_token(subject: str) -> str:
    settings = get_settings()
    to_encode = TokenPayload(
        sub=subject,
        exp=int(
            (datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()
        ),
    ).model_dump()
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


async def get_current_admin(credentials: Annotated[HTTPAuthorizationCredentials, Depends(oauth2_scheme)]) -> str:
    settings = get_settings()
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        token_payload = TokenPayload(**payload)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid credentials") from exc

    if token_payload.exp < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token expired")
    return token_payload.sub
