from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.deps import APIIdentity, api_identity
from app.models import ModelRoute, Provider, UsageLedger
from app.quotas import QuotaExceeded, Reservation
from app.schemas import ChatRequest
from app.security import decrypt_secret, validate_upstream_url
from app.services import estimate_tokens, monthly_usage, upstream_client

router = APIRouter(prefix="/v1", tags=["openai-compatible"])
settings = get_settings()


def openai_error(
    status_code: int,
    message: str,
    error_type: str,
    code: Optional[str] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    headers = {"x-request-id": request_id} if request_id else None
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content={"error": {"message": message, "type": error_type, "param": None, "code": code}},
    )


async def resolve_route(
    db: AsyncSession, identity: APIIdentity, alias: str
) -> Optional[ModelRoute]:
    if alias not in identity.user.allowed_models:
        return None
    result = await db.execute(
        select(ModelRoute)
        .options(selectinload(ModelRoute.provider))
        .where(ModelRoute.public_name == alias, ModelRoute.active.is_(True))
    )
    route = result.scalar_one_or_none()
    if not route or not route.provider.active:
        return None
    return route


async def reserve_quota(
    request: Request,
    db: AsyncSession,
    identity: APIIdentity,
    route: ModelRoute,
    payload: Dict[str, Any],
) -> tuple[Reservation, int]:
    input_tokens = estimate_tokens(payload.get("messages", []), route.tokenizer)
    requested_output = payload.get("max_completion_tokens") or payload.get("max_tokens")
    if requested_output is not None and requested_output > route.max_output_tokens:
        raise ValueError(f"最大输出 Token 不能超过 {route.max_output_tokens}")
    output_reserve = requested_output or route.max_output_tokens
    reserved = input_tokens + int(output_reserve)
    totals = await monthly_usage(db, identity.user.id)
    reservation = await request.app.state.quota.reserve(
        key_id=identity.access_key.id,
        user_id=identity.user.id,
        rpm_limit=min(identity.access_key.rpm_limit, identity.user.rpm_limit),
        tpm_limit=min(identity.access_key.tpm_limit, identity.user.tpm_limit),
        monthly_limit=identity.user.monthly_token_limit,
        tokens=reserved,
        baseline_monthly=totals["total_tokens"],
    )
    return reservation, input_tokens


async def record_usage(
    db: AsyncSession,
    *,
    request_id: str,
    identity: APIIdentity,
    alias: str,
    input_tokens: int,
    output_tokens: int,
    status_code: int,
    started: float,
    error_type: Optional[str] = None,
) -> None:
    db.add(
        UsageLedger(
            request_id=request_id,
            user_id=identity.user.id,
            access_key_id=identity.access_key.id,
            model_alias=alias,
            input_tokens=max(0, input_tokens),
            output_tokens=max(0, output_tokens),
            total_tokens=max(0, input_tokens + output_tokens),
            status_code=status_code,
            latency_ms=max(0, int((time.monotonic() - started) * 1000)),
            error_type=error_type,
        )
    )
    await db.commit()


@router.get("/models")
async def models(identity: APIIdentity = Depends(api_identity), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ModelRoute)
        .join(Provider, Provider.id == ModelRoute.provider_id)
        .where(
            ModelRoute.active.is_(True),
            Provider.active.is_(True),
            ModelRoute.public_name.in_(identity.user.allowed_models),
        )
    )
    now = int(datetime.now(timezone.utc).timestamp())
    data = [
        {"id": route.public_name, "object": "model", "created": now, "owned_by": "token-station"}
        for route in result.scalars()
        if route.active
    ]
    return {"object": "list", "data": data}


@router.post("/chat/completions")
async def chat_completions(
    chat: ChatRequest,
    request: Request,
    identity: APIIdentity = Depends(api_identity),
    db: AsyncSession = Depends(get_db),
):
    request_id = f"req_{uuid.uuid4().hex}"
    started = time.monotonic()
    alias = chat.model
    route = await resolve_route(db, identity, alias)
    if not route:
        return openai_error(
            404, "模型不存在或无权使用", "invalid_request_error", "model_not_found", request_id
        )
    payload = chat.model_dump(exclude_none=True)
    payload["model"] = route.upstream_model
    if chat.stream and route.provider.supports_stream_usage:
        stream_options = dict(payload.get("stream_options") or {})
        stream_options["include_usage"] = True
        payload["stream_options"] = stream_options
    try:
        reservation, estimated_input = await reserve_quota(request, db, identity, route, payload)
    except ValueError as exc:
        return openai_error(422, str(exc), "invalid_request_error", "max_tokens", request_id)
    except QuotaExceeded as exc:
        return openai_error(429, exc.message, "rate_limit_error", exc.code, request_id)
    try:
        await validate_upstream_url(route.provider.base_url, settings.allow_private_upstreams)
        upstream_key = decrypt_secret(
            route.provider.key_ciphertext,
            route.provider.key_nonce,
            route.provider.key_version,
            settings,
        )
    except ValueError:
        await request.app.state.quota.finalize(reservation, 0)
        await record_usage(
            db,
            request_id=request_id,
            identity=identity,
            alias=alias,
            input_tokens=0,
            output_tokens=0,
            status_code=502,
            started=started,
            error_type="provider_configuration_error",
        )
        return openai_error(502, "上游配置不可用", "api_error", "provider_error", request_id)

    headers = {
        "Authorization": f"Bearer {upstream_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if chat.stream else "application/json",
        "X-Client-Request-Id": request_id,
    }
    url = f"{route.provider.base_url}/chat/completions"
    if chat.stream:
        return await stream_chat(
            request,
            db,
            identity,
            route,
            alias,
            payload,
            headers,
            url,
            reservation,
            estimated_input,
            request_id,
            started,
        )
    return await regular_chat(
        request,
        db,
        identity,
        route,
        alias,
        payload,
        headers,
        url,
        reservation,
        estimated_input,
        request_id,
        started,
    )


async def regular_chat(
    request: Request,
    db: AsyncSession,
    identity: APIIdentity,
    route: ModelRoute,
    alias: str,
    payload: dict,
    headers: dict,
    url: str,
    reservation: Reservation,
    estimated_input: int,
    request_id: str,
    started: float,
):
    try:
        async with upstream_client(request.app, route.provider.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        await request.app.state.quota.finalize(reservation, 0)
        await record_usage(
            db,
            request_id=request_id,
            identity=identity,
            alias=alias,
            input_tokens=0,
            output_tokens=0,
            status_code=504,
            started=started,
            error_type="upstream_timeout",
        )
        return openai_error(504, "上游响应超时", "api_error", "upstream_timeout", request_id)
    except httpx.HTTPError:
        await request.app.state.quota.finalize(reservation, 0)
        await record_usage(
            db,
            request_id=request_id,
            identity=identity,
            alias=alias,
            input_tokens=0,
            output_tokens=0,
            status_code=502,
            started=started,
            error_type="upstream_connection_error",
        )
        return openai_error(502, "无法连接上游", "api_error", "upstream_unavailable", request_id)
    if response.status_code >= 400:
        await request.app.state.quota.finalize(reservation, 0)
        await record_usage(
            db,
            request_id=request_id,
            identity=identity,
            alias=alias,
            input_tokens=0,
            output_tokens=0,
            status_code=response.status_code,
            started=started,
            error_type="upstream_rejected",
        )
        status_code = (
            response.status_code if response.status_code in {400, 401, 403, 404, 429} else 502
        )
        return openai_error(
            status_code, "上游拒绝了请求", "api_error", "upstream_rejected", request_id
        )
    try:
        data = response.json()
    except ValueError:
        await request.app.state.quota.finalize(reservation, 0)
        await record_usage(
            db,
            request_id=request_id,
            identity=identity,
            alias=alias,
            input_tokens=0,
            output_tokens=0,
            status_code=502,
            started=started,
            error_type="invalid_upstream_response",
        )
        return openai_error(502, "上游返回了无效响应", "api_error", "invalid_response", request_id)
    if isinstance(data, dict):
        data["model"] = alias
    usage = data.get("usage") if isinstance(data, dict) else None
    input_tokens = int((usage or {}).get("prompt_tokens") or estimated_input)
    if usage and usage.get("completion_tokens") is not None:
        output_tokens = int(usage["completion_tokens"])
    else:
        output_tokens = estimate_tokens(data.get("choices", []), route.tokenizer)
    await request.app.state.quota.finalize(reservation, input_tokens + output_tokens)
    await record_usage(
        db,
        request_id=request_id,
        identity=identity,
        alias=alias,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        status_code=200,
        started=started,
    )
    return JSONResponse(content=data, headers={"x-request-id": request_id})


async def stream_chat(
    request: Request,
    db: AsyncSession,
    identity: APIIdentity,
    route: ModelRoute,
    alias: str,
    payload: dict,
    headers: dict,
    url: str,
    reservation: Reservation,
    estimated_input: int,
    request_id: str,
    started: float,
):
    client = upstream_client(request.app, route.provider.timeout_seconds)
    try:
        upstream_request = client.build_request("POST", url, headers=headers, json=payload)
        response = await client.send(upstream_request, stream=True)
    except httpx.TimeoutException:
        await client.aclose()
        await request.app.state.quota.finalize(reservation, 0)
        await record_usage(
            db,
            request_id=request_id,
            identity=identity,
            alias=alias,
            input_tokens=0,
            output_tokens=0,
            status_code=504,
            started=started,
            error_type="upstream_timeout",
        )
        return openai_error(504, "上游响应超时", "api_error", "upstream_timeout", request_id)
    except httpx.HTTPError:
        await client.aclose()
        await request.app.state.quota.finalize(reservation, 0)
        await record_usage(
            db,
            request_id=request_id,
            identity=identity,
            alias=alias,
            input_tokens=0,
            output_tokens=0,
            status_code=502,
            started=started,
            error_type="upstream_connection_error",
        )
        return openai_error(502, "无法连接上游", "api_error", "upstream_unavailable", request_id)
    if response.status_code >= 400:
        await response.aclose()
        await client.aclose()
        await request.app.state.quota.finalize(reservation, 0)
        await record_usage(
            db,
            request_id=request_id,
            identity=identity,
            alias=alias,
            input_tokens=0,
            output_tokens=0,
            status_code=response.status_code,
            started=started,
            error_type="upstream_rejected",
        )
        status_code = (
            response.status_code if response.status_code in {400, 401, 403, 404, 429} else 502
        )
        return openai_error(
            status_code, "上游拒绝了请求", "api_error", "upstream_rejected", request_id
        )

    async def event_stream():
        usage: Dict[str, Any] = {}
        output_parts: list[Any] = []
        status_code = 200
        error_type = None
        try:
            async for line in response.aiter_lines():
                if not line:
                    continue
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    yield b"data: [DONE]\n\n"
                    continue
                try:
                    event = json.loads(raw)
                    if not isinstance(event, dict):
                        raise TypeError("invalid SSE event")
                    if "error" in event:
                        status_code = 502
                        error_type = "upstream_stream_error"
                        event = {
                            "error": {
                                "message": "上游流式响应失败",
                                "type": "api_error",
                                "param": None,
                                "code": "upstream_stream_error",
                            }
                        }
                    else:
                        event["model"] = alias
                        if isinstance(event.get("usage"), dict):
                            usage.update(event["usage"])
                        for choice in event.get("choices") or []:
                            delta = choice.get("delta") or {}
                            if delta:
                                output_parts.append(delta)
                    yield ("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode(
                        "utf-8"
                    )
                except (ValueError, TypeError):
                    status_code = 502
                    error_type = "invalid_upstream_stream"
                    safe_event = {
                        "error": {
                            "message": "上游返回了无效流式响应",
                            "type": "api_error",
                            "param": None,
                            "code": "invalid_upstream_stream",
                        }
                    }
                    yield ("data: " + json.dumps(safe_event, ensure_ascii=False) + "\n\n").encode(
                        "utf-8"
                    )
                    yield b"data: [DONE]\n\n"
                    break
        except asyncio.CancelledError:
            status_code = 499
            error_type = "client_disconnected"
            raise
        except (httpx.HTTPError, asyncio.TimeoutError):
            status_code = 502
            error_type = "stream_interrupted"
            error_event = {
                "error": {
                    "message": "上游流式响应中断",
                    "type": "api_error",
                    "param": None,
                    "code": "stream_interrupted",
                }
            }
            yield ("data: " + json.dumps(error_event, ensure_ascii=False) + "\n\n").encode("utf-8")
            yield b"data: [DONE]\n\n"
        finally:
            await response.aclose()
            await client.aclose()
            input_tokens = int(usage.get("prompt_tokens") or estimated_input)
            output_tokens = int(
                usage.get("completion_tokens")
                if usage.get("completion_tokens") is not None
                else estimate_tokens(output_parts, route.tokenizer)
            )
            actual = input_tokens + output_tokens
            await request.app.state.quota.finalize(reservation, actual)
            try:
                await record_usage(
                    db,
                    request_id=request_id,
                    identity=identity,
                    alias=alias,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    status_code=status_code,
                    started=started,
                    error_type=error_type,
                )
            except Exception:
                await db.rollback()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "x-request-id": request_id,
        },
    )
