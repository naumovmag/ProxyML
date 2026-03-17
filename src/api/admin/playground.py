import uuid
import time
import json
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from sqlalchemy import select, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_admin
from src.services.service_registry import get_service_by_id
from src.models.admin_user import AdminUser
from src.models.playground import PlaygroundPreset, PlaygroundHistory
from src.proxy.client import get_http_client

logger = logging.getLogger(__name__)
router = APIRouter()


class PlaygroundRequest(BaseModel):
    service_id: uuid.UUID
    method: str = "POST"
    path: str = ""
    body: dict | list | str | None = None
    headers: dict[str, str] | None = None
    stream: bool = False


class PlaygroundResponse(BaseModel):
    status_code: int
    headers: dict[str, str]
    body: str
    duration_ms: float
    response_size: int


def _build_target(service, path: str) -> str:
    base = service.base_url.rstrip("/")
    if path:
        return f"{base}/{path.lstrip('/')}"
    return base


def _apply_auth(headers: dict, service) -> str | None:
    """Apply service auth to headers. Returns modified target_url suffix or None."""
    if service.auth_type == "bearer":
        headers["Authorization"] = f"Bearer {service.auth_token}"
    elif service.auth_type == "header":
        header_name = service.auth_header_name or "Authorization"
        headers[header_name] = service.auth_token or ""
    elif service.auth_type == "query_param":
        return f"api_key={service.auth_token or ''}"
    return None


@router.post("/playground/execute")
async def playground_execute(
    data: PlaygroundRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    service = await get_service_by_id(session, data.service_id)
    if not service or service.owner_id != admin.id:
        raise HTTPException(status_code=404, detail="Service not found")

    target_url = _build_target(service, data.path)

    # Build headers
    headers = {"Content-Type": "application/json"}
    if service.extra_headers:
        headers.update(service.extra_headers)
    if data.headers:
        headers.update(data.headers)

    query_suffix = _apply_auth(headers, service)
    if query_suffix:
        sep = "&" if "?" in target_url else "?"
        target_url += f"{sep}{query_suffix}"

    # Body
    content: bytes | None = None
    if data.body is not None:
        if isinstance(data.body, str):
            content = data.body.encode()
        else:
            content = json.dumps(data.body).encode()

    timeout = httpx.Timeout(float(service.timeout_seconds), connect=10.0)
    client = await get_http_client()
    start = time.monotonic()

    try:
        # Streaming
        if data.stream and service.supports_streaming:
            req = client.build_request(
                method=data.method,
                url=target_url,
                headers=headers,
                content=content,
                timeout=timeout,
            )
            response = await client.send(req, stream=True)

            resp_headers = dict(response.headers)
            for h in ("transfer-encoding", "connection", "content-length"):
                resp_headers.pop(h, None)

            async def stream_gen():
                try:
                    async for chunk in response.aiter_bytes():
                        yield chunk
                finally:
                    await response.aclose()

            return StreamingResponse(
                stream_gen(),
                status_code=response.status_code,
                headers=resp_headers,
                media_type=response.headers.get("content-type", "text/event-stream"),
            )

        # Non-streaming
        response = await client.request(
            method=data.method,
            url=target_url,
            headers=headers,
            content=content,
            timeout=timeout,
        )
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        resp_headers = {}
        for k, v in response.headers.items():
            if k.lower() not in ("transfer-encoding", "connection", "content-encoding"):
                resp_headers[k] = v

        content_type = response.headers.get("content-type", "")

        # Binary response (e.g. TTS audio)
        if "audio" in content_type or "octet-stream" in content_type:
            resp_headers["X-Playground-Duration-Ms"] = str(duration_ms)
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=resp_headers,
                media_type=content_type,
            )

        body_text = response.text
        return PlaygroundResponse(
            status_code=response.status_code,
            headers=resp_headers,
            body=body_text,
            duration_ms=duration_ms,
            response_size=len(response.content),
        )

    except httpx.TimeoutException:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        raise HTTPException(status_code=504, detail=f"Backend timeout after {duration_ms}ms")
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"Connection failed: {str(e)}")
    except Exception as e:
        logger.error(f"Playground error: {e}")
        raise HTTPException(status_code=502, detail=f"Proxy error: {str(e)}")


@router.post("/playground/upload")
async def playground_upload(
    service_id: str = Form(...),
    path: str = Form("v1/audio/transcriptions"),
    model: str = Form(None),
    file: UploadFile = File(...),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    service = await get_service_by_id(session, uuid.UUID(service_id))
    if not service or service.owner_id != admin.id:
        raise HTTPException(status_code=404, detail="Service not found")

    target_url = _build_target(service, path)

    headers: dict[str, str] = {}
    if service.extra_headers:
        headers.update(service.extra_headers)

    query_suffix = _apply_auth(headers, service)
    if query_suffix:
        sep = "&" if "?" in target_url else "?"
        target_url += f"{sep}{query_suffix}"

    timeout = httpx.Timeout(float(service.timeout_seconds), connect=10.0)
    client = await get_http_client()
    start = time.monotonic()

    file_content = await file.read()
    files = {"file": (file.filename, file_content, file.content_type or "application/octet-stream")}
    data_fields: dict[str, str] = {}
    if model:
        data_fields["model"] = model

    try:
        response = await client.post(
            target_url,
            headers=headers,
            files=files,
            data=data_fields,
            timeout=timeout,
        )
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        resp_headers = {}
        for k, v in response.headers.items():
            if k.lower() not in ("transfer-encoding", "connection", "content-encoding"):
                resp_headers[k] = v

        return PlaygroundResponse(
            status_code=response.status_code,
            headers=resp_headers,
            body=response.text,
            duration_ms=duration_ms,
            response_size=len(response.content),
        )
    except httpx.TimeoutException:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        raise HTTPException(status_code=504, detail=f"Backend timeout after {duration_ms}ms")
    except Exception as e:
        logger.error(f"Playground upload error: {e}")
        raise HTTPException(status_code=502, detail=f"Proxy error: {str(e)}")


# ─── Presets ───


class PresetCreate(BaseModel):
    service_id: str
    service_type: str
    name: str
    params: dict


class PresetUpdate(BaseModel):
    name: str | None = None
    params: dict | None = None


class PresetRead(BaseModel):
    id: str
    service_id: str | None
    service_type: str
    name: str
    params: dict
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


def _preset_to_read(p: PlaygroundPreset) -> PresetRead:
    return PresetRead(
        id=str(p.id), service_id=str(p.service_id) if p.service_id else None,
        service_type=p.service_type, name=p.name,
        params=p.params, created_at=p.created_at.isoformat(), updated_at=p.updated_at.isoformat(),
    )


@router.get("/playground/presets")
async def list_presets(
    service_id: str | None = Query(None),
    service_type: str | None = Query(None),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    q = select(PlaygroundPreset).where(PlaygroundPreset.owner_id == admin.id)
    if service_id:
        q = q.where(PlaygroundPreset.service_id == uuid.UUID(service_id))
    elif service_type:
        q = q.where(PlaygroundPreset.service_type == service_type)
    q = q.order_by(PlaygroundPreset.updated_at.desc())
    result = await session.execute(q)
    presets = result.scalars().all()
    return [_preset_to_read(p) for p in presets]


@router.post("/playground/presets")
async def create_preset(
    data: PresetCreate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    preset = PlaygroundPreset(
        owner_id=admin.id,
        service_id=uuid.UUID(data.service_id),
        service_type=data.service_type,
        name=data.name,
        params=data.params,
    )
    session.add(preset)
    await session.commit()
    await session.refresh(preset)
    return _preset_to_read(preset)


@router.put("/playground/presets/{preset_id}")
async def update_preset(
    preset_id: uuid.UUID,
    data: PresetUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(PlaygroundPreset).where(PlaygroundPreset.id == preset_id, PlaygroundPreset.owner_id == admin.id)
    )
    preset = result.scalar_one_or_none()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    if data.name is not None:
        preset.name = data.name
    if data.params is not None:
        preset.params = data.params
    await session.commit()
    await session.refresh(preset)
    return _preset_to_read(preset)


@router.delete("/playground/presets/{preset_id}")
async def delete_preset(
    preset_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(PlaygroundPreset).where(PlaygroundPreset.id == preset_id, PlaygroundPreset.owner_id == admin.id)
    )
    preset = result.scalar_one_or_none()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    await session.delete(preset)
    await session.commit()
    return {"ok": True}


# ─── History ───


class HistorySave(BaseModel):
    service_id: str
    service_name: str
    service_type: str
    params: dict | None = None
    request_body: str | None = None
    response_body: str | None = None
    status_code: int | None = None
    duration_ms: float | None = None
    token_usage: dict | None = None
    note: str | None = None


class HistoryRead(BaseModel):
    id: str
    service_id: str | None
    service_name: str | None
    service_type: str | None
    params: dict | None
    request_body: str | None
    response_body: str | None
    status_code: int | None
    duration_ms: float | None
    token_usage: dict | None
    note: str | None
    is_favorite: bool
    created_at: str

    model_config = {"from_attributes": True}


class HistoryUpdateNote(BaseModel):
    note: str | None = None
    is_favorite: bool | None = None


@router.get("/playground/history")
async def list_history(
    service_id: str | None = Query(None),
    favorites_only: bool = Query(False),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    q = select(PlaygroundHistory).where(PlaygroundHistory.owner_id == admin.id)
    if service_id:
        q = q.where(PlaygroundHistory.service_id == uuid.UUID(service_id))
    if favorites_only:
        q = q.where(PlaygroundHistory.is_favorite.is_(True))
    q = q.order_by(desc(PlaygroundHistory.created_at)).offset(offset).limit(limit)
    result = await session.execute(q)
    items = result.scalars().all()
    return [
        HistoryRead(
            id=str(h.id),
            service_id=str(h.service_id) if h.service_id else None,
            service_name=h.service_name, service_type=h.service_type,
            params=h.params, request_body=h.request_body, response_body=h.response_body,
            status_code=h.status_code, duration_ms=h.duration_ms, token_usage=h.token_usage,
            note=h.note, is_favorite=h.is_favorite, created_at=h.created_at.isoformat(),
        )
        for h in items
    ]


@router.post("/playground/history")
async def save_history(
    data: HistorySave,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    entry = PlaygroundHistory(
        owner_id=admin.id,
        service_id=uuid.UUID(data.service_id),
        service_name=data.service_name,
        service_type=data.service_type,
        params=data.params,
        request_body=data.request_body,
        response_body=data.response_body,
        status_code=data.status_code,
        duration_ms=data.duration_ms,
        token_usage=data.token_usage,
        note=data.note,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return HistoryRead(
        id=str(entry.id),
        service_id=str(entry.service_id) if entry.service_id else None,
        service_name=entry.service_name, service_type=entry.service_type,
        params=entry.params, request_body=entry.request_body, response_body=entry.response_body,
        status_code=entry.status_code, duration_ms=entry.duration_ms, token_usage=entry.token_usage,
        note=entry.note, is_favorite=entry.is_favorite, created_at=entry.created_at.isoformat(),
    )


@router.put("/playground/history/{entry_id}")
async def update_history(
    entry_id: uuid.UUID,
    data: HistoryUpdateNote,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(PlaygroundHistory).where(PlaygroundHistory.id == entry_id, PlaygroundHistory.owner_id == admin.id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    if data.note is not None:
        entry.note = data.note
    if data.is_favorite is not None:
        entry.is_favorite = data.is_favorite
    await session.commit()
    await session.refresh(entry)
    return HistoryRead(
        id=str(entry.id),
        service_id=str(entry.service_id) if entry.service_id else None,
        service_name=entry.service_name, service_type=entry.service_type,
        params=entry.params, request_body=entry.request_body, response_body=entry.response_body,
        status_code=entry.status_code, duration_ms=entry.duration_ms, token_usage=entry.token_usage,
        note=entry.note, is_favorite=entry.is_favorite, created_at=entry.created_at.isoformat(),
    )


@router.delete("/playground/history/{entry_id}")
async def delete_history(
    entry_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(PlaygroundHistory).where(PlaygroundHistory.id == entry_id, PlaygroundHistory.owner_id == admin.id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    await session.delete(entry)
    await session.commit()
    return {"ok": True}


@router.delete("/playground/history")
async def clear_history(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await session.execute(
        delete(PlaygroundHistory).where(PlaygroundHistory.owner_id == admin.id)
    )
    await session.commit()
    return {"ok": True}
