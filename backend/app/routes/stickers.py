from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas
from ..auth import get_current_admin
from ..database import get_session
from ..models import Sticker

router = APIRouter(prefix="/stickers", tags=["stickers"])


@router.get("/", response_model=list[schemas.Sticker])
async def list_stickers(session: Annotated[AsyncSession, Depends(get_session)], include_inactive: bool = False):
    query = select(Sticker)
    if not include_inactive:
        query = query.where(Sticker.active.is_(True))
    result = await session.execute(query.order_by(Sticker.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=schemas.Sticker)
async def create_sticker(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[str, Depends(get_current_admin)],
    name: Annotated[str, Form(...)],
    price_cents: Annotated[int, Form(...)],
    description: Annotated[str | None, Form()] = None,
    currency: Annotated[str, Form()] = "usd",
    active: Annotated[bool, Form()] = True,
    image: Annotated[str | None, Form()] = None,
):
    if price_cents <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Price must be positive")

    image_url = None
    if image is not None:
        image_url = await save_image(image)

    sticker = Sticker(
        name=name,
        description=description,
        price_cents=price_cents,
        currency=currency,
        active=active,
        image_url=image_url,
    )
    session.add(sticker)
    await session.commit()
    await session.refresh(sticker)
    return sticker


@router.patch("/{sticker_id}", response_model=schemas.Sticker)
async def update_sticker(
    sticker_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[str, Depends(get_current_admin)],
):
    sticker = await session.get(Sticker, sticker_id)
    if not sticker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sticker not found")

    content_type = request.headers.get("content-type", "")
    update_fields: dict[str, object] = {}

    if content_type.startswith("application/json"):
        payload = schemas.StickerUpdate(**await request.json())
        update_fields = payload.model_dump(exclude_unset=True)
    elif content_type.startswith("multipart/form-data"):
        update_fields = await parse_form_update(request)
    else:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported content type")

    if not update_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update values provided")

    price = update_fields.get("price_cents")
    if isinstance(price, int) and price <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Price must be positive")

    name = update_fields.get("name")
    if isinstance(name, str) and not name.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name cannot be empty")

    currency = update_fields.get("currency")
    if isinstance(currency, str):
        update_fields["currency"] = currency.lower()

    for field, value in update_fields.items():
        setattr(sticker, field, value)

    await session.commit()
    await session.refresh(sticker)
    return sticker


@router.delete("/{sticker_id}")
async def delete_sticker(
    sticker_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[str, Depends(get_current_admin)],
):
    sticker = await session.get(Sticker, sticker_id)
    if not sticker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sticker not found")
    await session.delete(sticker)
    await session.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={})


async def save_image(upload: UploadFile) -> str:
    static_dir = Path(__file__).resolve().parents[2] / "static" / "stickers"
    static_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(upload.filename or "").suffix or ".png"
    destination = static_dir / f"{uuid4().hex}{suffix}"

    data = await upload.read()
    destination.write_bytes(data)
    rel_path = destination.relative_to(Path(__file__).resolve().parents[2])
    return f"/{rel_path.as_posix()}"


async def parse_form_update(request: Request) -> dict[str, object]:
    form = await request.form()
    update: dict[str, object] = {}

    for field in ("name", "description", "currency"):
        if field in form:
            value = form.get(field)
            if field in {"name", "currency"} and value in (None, ""):
                continue
            update[field] = value

    if "price_cents" in form:
        price_raw = form.get("price_cents")
        if price_raw not in (None, ""):
            try:
                update["price_cents"] = int(price_raw)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Price must be an integer",
                ) from exc

    if "active" in form:
        update["active"] = str(form.get("active")).lower() in {"true", "1", "on", "yes"}

    image = form.get("image")
    if isinstance(image, UploadFile) and image.filename:
        update["image_url"] = await save_image(image)

    if update:
        payload = schemas.StickerUpdate(**update)
        return payload.model_dump(exclude_unset=True)
    return {}
