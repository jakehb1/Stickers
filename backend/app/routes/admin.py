from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ..auth import authenticate_admin, create_access_token, get_current_admin
from ..schemas import Token

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=Token)
async def admin_login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    is_valid = await authenticate_admin(form_data.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    token = create_access_token("admin")
    return Token(access_token=token)


@router.get("/me")
async def admin_me(_: Annotated[str, Depends(get_current_admin)]):
    return {"role": "admin"}
