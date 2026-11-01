"""Shared stateless Chat Completions / Responses transport and metering."""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid

import anyio
import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.deps import APIIdentity, api_identity
from app.model_policy import prepare_payload
from app.models import ModelRoute, Provider, UsageLedger
from app.quotas import QuotaExceeded
from app.schemas import ChatRequest, ResponsesRequest
from app.security import decrypt_secret, validate_upstream_url
from app.services import estimate_tokens, monthly_usage, upstream_client

router = APIRouter(prefix="/v1", tags=["openai-compatible"])
settings = get_settings()
MAX_EVENT_BYTES = 4 * 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024


async def while_connected(request, operation):
    """Abort upstream work even before response headers when the client disappears."""
    stop = asyncio.Event()

    async def disconnected():
        while not stop.is_set() and not await request.is_disconnected():
            await asyncio.sleep(0.2)

    task = asyncio.create_task(operation)
    watch = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait({task, watch}, return_when=asyncio.FIRST_COMPLETED)
        if watch in done:
            raise asyncio.CancelledError
        return await task
    finally:
        stop.set()
        task.cancel()
        watch.cancel()
        with anyio.CancelScope(shield=True):
            await asyncio.gather(task, watch, return_exceptions=True)


def error_body(message, code, request_id):
    return {
        "error": {
            "message": message,
            "type": "api_error",
            "param": None,
            "code": code,
            "request_id": request_id,
        }
    }


def openai_error(status, message, code, request_id):
    return JSONResponse(
        status_code=status,
        content=error_body(message, code, request_id),
        headers={"x-request-id": request_id},
    )


def scrub(value, secret):
    """Redact provider credentials even if an upstream echoes them in successful output."""
    if isinstance(value, str):
        return value.replace(secret, "[redacted]")
    if isinstance(value, dict):
        return {scrub(k, secret): scrub(v, secret) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, secret) for v in value]
    return value


def usage_counts(usage, protocol):
    if not isinstance(usage, dict):
        return None
    fields = (
        ("input_tokens", "output_tokens")
        if protocol == "responses"
        else ("prompt_tokens", "completion_tokens")
    )
    values = tuple(usage.get(k) for k in fields)
    if all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 10**9 for v in values):
        return values
    return None


async def sse_events(response):
    """Parse complete frames, preserving multiline JSON and bounding frame memory."""
    event, data, size = "", [], 0
    async for line in response.aiter_lines():
        size += len(line.encode("utf-8"))
        if size > MAX_EVENT_BYTES:
            raise ValueError("oversized event")
        if not line:
            if data:
                yield event, "\n".join(data)
            event, data, size = "", [], 0
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data:
        yield event, "\n".join(data)


def encode_event(data, name=""):
    if name and not re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", name):
        raise ValueError("invalid event name")
    prefix = f"event: {name}\n" if name else ""
    return (prefix + "data: " + json.dumps(data, ensure_ascii=False) + "\n\n").encode()


@router.get("/models")
async def models(identity: APIIdentity = Depends(api_identity), db: AsyncSession = Depends(get_db)):
    routes = await db.scalars(
        select(ModelRoute)
        .join(Provider)
        .where(
            ModelRoute.active.is_(True),
            Provider.active.is_(True),
            ModelRoute.public_name.in_(identity.user.allowed_models),
        )
    )
    return {
        "object": "list",
        "data": [
            {
                "id": r.public_name,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "token-station",
                "api_mode": r.api_mode,
                "reasoning_effort": r.reasoning_effort,
            }
            for r in routes
        ],
    }


@router.post("/chat/completions")
async def chat_completions(
    chat: ChatRequest,
    request: Request,
    identity: APIIdentity = Depends(api_identity),
    db: AsyncSession = Depends(get_db),
):
    return await relay(chat.model_dump(exclude_none=True), "chat", request, identity, db)


@router.post("/responses")
async def responses(
    body: ResponsesRequest,
    request: Request,
    identity: APIIdentity = Depends(api_identity),
    db: AsyncSession = Depends(get_db),
):
    return await relay(body.model_dump(exclude_none=True), "responses", request, identity, db)


async def relay(payload, protocol, request, identity, db):
    request_id, started = f"req_{uuid.uuid4().hex}", time.monotonic()
    alias = payload["model"]
    route = None
    if alias in identity.user.allowed_models:
        route = await db.scalar(
            select(ModelRoute)
            .options(selectinload(ModelRoute.provider))
            .where(ModelRoute.public_name == alias, ModelRoute.active.is_(True))
        )
    if route is None or not route.provider.active:
        return openai_error(404, "模型不存在或无权使用", "model_not_found", request_id)
    try:
        payload = prepare_payload(route, payload, protocol)
    except (ValueError, TypeError) as exc:
        message = str(exc) if isinstance(exc, ValueError) else "请求参数格式错误"
        return openai_error(422, message, "invalid_request_error", request_id)
    if protocol == "chat" and payload.get("stream") and route.provider.supports_stream_usage:
        payload["stream_options"] = {**(payload.get("stream_options") or {}), "include_usage": True}
    fields = (
        ("messages", "tools", "functions", "response_format")
        if protocol == "chat"
        else ("input", "instructions", "tools", "text")
    )
    estimated = estimate_tokens({k: payload[k] for k in fields if k in payload}, route.tokenizer)
    budget = (
        payload.get("max_output_tokens")
        or payload.get("max_completion_tokens")
        or payload.get("max_tokens")
    )
    try:
        await validate_upstream_url(route.provider.base_url, settings.allow_private_upstreams)
        secret = decrypt_secret(
            route.provider.key_ciphertext,
            route.provider.key_nonce,
            route.provider.key_version,
            settings,
        )
    except (ValueError, OSError):
        return openai_error(502, "上游配置不可用", "provider_configuration_error", request_id)
    totals = await monthly_usage(db, identity.user.id)
    # Do not hold a read transaction for the lifetime of an upstream stream.
    # Settlement needs its own connection; retaining all readers can exhaust the pool.
    await db.close()
    try:
        reservation = await request.app.state.quota.reserve(
            key_id=identity.access_key.id,
            user_id=identity.user.id,
            rpm_limit=min(identity.access_key.rpm_limit, identity.user.rpm_limit),
            tpm_limit=min(identity.access_key.tpm_limit, identity.user.tpm_limit),
            monthly_limit=identity.user.monthly_token_limit,
            tokens=estimated + budget,
            baseline_monthly=totals["total_tokens"],
        )
    except QuotaExceeded as exc:
        return openai_error(429, exc.message, exc.code, request_id)
    settled = False

    async def settle(counts, status, error=None, started_upstream=True):
        nonlocal settled
        if settled:
            return
        settled = True
        # Hidden reasoning and partial/disconnected output cannot be measured from text alone.
        inputs, outputs = counts or ((estimated, budget) if started_upstream else (0, 0))
        with anyio.CancelScope(shield=True):
            await request.app.state.quota.finalize(reservation, inputs + outputs)
            async with SessionLocal() as ledger_db:
                ledger_db.add(
                    UsageLedger(
                        request_id=request_id,
                        user_id=identity.user.id,
                        access_key_id=identity.access_key.id,
                        model_alias=alias,
                        input_tokens=inputs,
                        output_tokens=outputs,
                        total_tokens=inputs + outputs,
                        status_code=status,
                        latency_ms=int((time.monotonic() - started) * 1000),
                        error_type=error,
                    )
                )
                await ledger_db.commit()

    client = upstream_client(request.app, route.provider.timeout_seconds)
    response = None

    async def close():
        with anyio.CancelScope(shield=True):
            if response is not None:
                await response.aclose()
            await client.aclose()

    url = f"{route.provider.base_url.rstrip('/')}/" + (
        "responses" if protocol == "responses" else "chat/completions"
    )
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if payload.get("stream") else "application/json",
        "X-Client-Request-Id": request_id,
    }
    try:
        response = await while_connected(
            request,
            client.send(
                client.build_request("POST", url, json=payload, headers=headers), stream=True
            ),
        )
        if not 200 <= response.status_code < 300:
            status = (
                response.status_code if response.status_code in {400, 401, 403, 404, 429} else 502
            )
            await settle(None, status, "upstream_rejected", False)
            await close()
            return openai_error(status, "上游拒绝了请求", "upstream_rejected", request_id)
        if payload.get("stream"):
            if "text/event-stream" not in response.headers.get("content-type", ""):
                raise ValueError("invalid stream content type")
            return StreamingResponse(
                stream_events(response, protocol, alias, secret, request_id, settle, close),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "x-request-id": request_id,
                },
            )

        async def read_body():
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise ValueError("oversized response")
            return content

        content = await while_connected(request, read_body())
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("invalid response")
        counts = usage_counts(data.get("usage"), protocol)
        if data.get("error") or data.get("status") in {"failed", "cancelled"}:
            await settle(counts, 502, "upstream_failed")
            await close()
            return openai_error(502, "上游生成失败", "upstream_failed", request_id)
        if protocol == "responses":
            if data.get("object") != "response" or not isinstance(data.get("output"), list):
                raise ValueError("invalid response object")
        elif not isinstance(data.get("choices"), list):
            raise ValueError("invalid choices")
        data["model"] = alias
        data = scrub(data, secret)
        await settle(counts, 200)
        await close()
        return JSONResponse(data, headers={"x-request-id": request_id})
    except asyncio.CancelledError:
        await close()
        await settle(None, 499, "client_disconnected")
        raise
    except httpx.TimeoutException as exc:
        await close()
        await settle(None, 504, "upstream_timeout", not isinstance(exc, httpx.ConnectTimeout))
        return openai_error(504, "上游响应超时", "upstream_timeout", request_id)
    except httpx.HTTPError as exc:
        await close()
        await settle(
            None, 502, "upstream_connection_error", not isinstance(exc, httpx.ConnectError)
        )
        return openai_error(502, "上游连接失败", "upstream_connection_error", request_id)
    except (ValueError, TypeError):
        await close()
        await settle(None, 502, "invalid_upstream_response")
        return openai_error(502, "上游返回了无效响应", "invalid_upstream_response", request_id)


async def stream_events(response, protocol, alias, secret, request_id, settle, close):
    counts, status, error, terminal = None, 200, None, False
    try:
        async for name, raw in sse_events(response):
            if raw == "[DONE]" and protocol == "chat":
                terminal = True
                yield b"data: [DONE]\n\n"
                break
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("invalid stream object")
            if protocol == "responses":
                kind = data.get("type", name)
                if not isinstance(kind, str) or (
                    not kind.startswith("response.") and kind != "error"
                ):
                    raise ValueError("invalid response event")
                name = kind
                inner = data.get("response")
                if isinstance(inner, dict):
                    inner["model"] = alias
                    counts = usage_counts(inner.get("usage"), protocol) or counts
                if kind in {"error", "response.failed"} or (
                    isinstance(inner, dict) and inner.get("error")
                ):
                    raise ValueError("failed stream")
                terminal = kind in {"response.completed", "response.incomplete"}
            else:
                if data.get("error"):
                    raise ValueError("failed stream")
                data["model"] = alias
                counts = usage_counts(data.get("usage"), protocol) or counts
            yield encode_event(scrub(data, secret), name)
            if terminal:
                break
        if not terminal:
            raise ValueError("truncated stream")
    except (asyncio.CancelledError, GeneratorExit):
        status, error = 499, "client_disconnected"
        raise
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        status = 504 if isinstance(exc, httpx.TimeoutException) else 502
        error = "upstream_timeout" if status == 504 else "upstream_stream_error"
        safe = error_body("上游流式响应中断", error, request_id)
        if protocol == "responses":
            safe = {
                "type": "error",
                "code": error,
                "message": "上游流式响应中断",
                "param": None,
                "request_id": request_id,
            }
        yield encode_event(safe, "error" if protocol == "responses" else "")
        if protocol == "chat":
            yield b"data: [DONE]\n\n"
    finally:
        await close()
        await settle(counts, status, error)
