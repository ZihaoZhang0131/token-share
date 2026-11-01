import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.gateway import stream_events, while_connected
from app.main import app
from app.models import AccessKey, ModelRoute, Provider, UsageLedger, User
from app.security import encrypt_secret, generate_access_key, hash_password

SECRET = "sk-gateway-test-upstream-secret"


@pytest.fixture
def relay_client(monkeypatch):
    async def safe_url(url, allow_private=False):
        return url

    monkeypatch.setattr("app.gateway.validate_upstream_url", safe_url)
    with TestClient(app) as client:

        async def seed():
            async with SessionLocal() as db:
                import uuid

                tag = uuid.uuid4().hex[:10]
                encrypted = encrypt_secret(SECRET, get_settings())
                provider = Provider(
                    name=tag,
                    base_url="https://example.com/v1",
                    key_ciphertext=encrypted.ciphertext,
                    key_nonce=encrypted.nonce,
                    key_version=encrypted.version,
                    key_last4=encrypted.last4,
                    timeout_seconds=10,
                    supports_stream_usage=True,
                )
                db.add(provider)
                await db.flush()
                aliases = [
                    f"{tag}-{effort}" for effort in ("low", "medium", "high", "xhigh", "max")
                ]
                for alias in aliases:
                    db.add(
                        ModelRoute(
                            public_name=alias,
                            upstream_model="gpt-6.1-sol",
                            provider_id=provider.id,
                            api_mode="both",
                            reasoning_effort=alias.split("-")[-1],
                            max_output_tokens=256,
                        )
                    )
                user = User(
                    email=f"{tag}@example.com",
                    display_name="test",
                    password_hash=hash_password("TestPassword!567"),
                    must_change_password=False,
                    monthly_token_limit=1000000,
                    rpm_limit=1000,
                    tpm_limit=1000000,
                    allowed_models=aliases,
                )
                db.add(user)
                await db.flush()
                plaintext, prefix, digest, last4 = generate_access_key()
                db.add(
                    AccessKey(
                        user_id=user.id,
                        name="test",
                        prefix=prefix,
                        secret_hash=digest,
                        last4=last4,
                        rpm_limit=1000,
                        tpm_limit=1000000,
                    )
                )
                await db.commit()
                return aliases, plaintext, user.id

        aliases, key, uid = client.portal.call(seed)
        client.headers["Authorization"] = f"Bearer {key}"
        yield client, aliases, uid
        if hasattr(app.state, "upstream_transport"):
            del app.state.upstream_transport


def completion(body, usage=True):
    data = {
        "id": "resp_test",
        "object": "response",
        "status": "completed",
        "model": "gpt-6.1-sol",
        "output": [
            {
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": "read_file",
                "arguments": "{}",
                "status": "completed",
            },
            {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "opaque"},
        ],
        "echo": body.get("input"),
    }
    if usage:
        data["usage"] = {
            "input_tokens": 12,
            "output_tokens": 8,
            "total_tokens": 20,
            "output_tokens_details": {"reasoning_tokens": 6},
        }
    return data


def test_all_efforts_both_protocols_and_headers(relay_client):
    client, aliases, uid = relay_client
    seen = []

    def upstream(req):
        body = json.loads(req.content)
        seen.append(body)
        assert req.headers["Authorization"] == f"Bearer {SECRET}"
        assert all(h not in req.headers for h in ("cookie", "x-forwarded-for", "x-private"))
        assert req.headers["host"] == "example.com"
        assert body["model"] == "gpt-6.1-sol" and body["store"] is False
        if req.url.path.endswith("responses"):
            assert body["reasoning"]["effort"] in {"low", "medium", "high", "xhigh", "max"}
            data = completion(body)
            data["debug"] = SECRET
        else:
            assert body["reasoning_effort"] in {"low", "medium", "high", "xhigh", "max"}
            assert body["max_completion_tokens"] == 256
            data = {
                "model": "gpt-6.1-sol",
                "choices": [],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8},
            }
        return httpx.Response(200, json=data, headers={"x-provider-secret": SECRET})

    app.state.upstream_transport = httpx.MockTransport(upstream)
    for alias in aliases:
        for endpoint, body in [
            ("responses", {"input": "hello"}),
            ("chat/completions", {"messages": [{"role": "user", "content": "hi"}]}),
        ]:
            r = client.post(
                "/v1/" + endpoint,
                json={"model": alias, **body},
                headers={"Cookie": "private=1", "x-private": "secret"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["model"] == alias and SECRET not in r.text
            assert "x-provider-secret" not in r.headers
    assert len(seen) == 10

    async def check():
        async with SessionLocal() as db:
            rows = list(await db.scalars(select(UsageLedger).where(UsageLedger.user_id == uid)))
            assert len(rows) == 10 and sum(r.total_tokens for r in rows) == 200

    client.portal.call(check)


@pytest.mark.parametrize(
    "extra",
    [
        {"reasoning": {"effort": "max"}},
        {"reasoning": {"effort": "none"}},
        {"previous_response_id": "resp_other_user"},
        {"conversation": "conv_other"},
        {"store": True},
        {"background": True},
        {"prompt": {"id": "pmpt_private"}},
        {"tools": [{"type": "file_search", "vector_store_ids": ["vs_private"]}]},
        {"tools": [{"type": "namespace", "name": "bad", "tools": [{"type": "web_search"}]}]},
        {"input": [{"type": "item_reference", "id": "msg_private"}]},
        {"input": [{"type": "input_file", "file_id": "file_private"}]},
        {"input": [{"type": "additional_tools", "tools": [{"type": "mcp"}]}]},
        {"max_output_tokens": 257},
        {"max_tokens": 8},
        {"temperature": 0.5},
        {"tools": "invalid"},
        {"reasoning": "high"},
    ],
)
def test_rejected_before_upstream(relay_client, extra):
    client, aliases, _ = relay_client

    def upstream(req):
        pytest.fail("invalid policy must not reach upstream")

    app.state.upstream_transport = httpx.MockTransport(upstream)
    r = client.post("/v1/responses", json={"model": aliases[2], "input": "hi", **extra})
    assert r.status_code == 422


def test_stateless_tools_roundtrip(relay_client):
    client, aliases, _ = relay_client
    seen = []

    def upstream(req):
        body = json.loads(req.content)
        seen.append(body)
        return httpx.Response(200, json=completion(body))

    app.state.upstream_transport = httpx.MockTransport(upstream)
    tools = [{"type": "namespace", "name": "local", "tools": [{"type": "custom", "name": "patch"}]}]
    first = client.post(
        "/v1/responses", json={"model": aliases[2], "input": "read", "tools": tools}
    ).json()
    history = [
        {"role": "user", "content": "read"},
        *first["output"],
        {"type": "function_call_output", "call_id": "call_1", "output": "file content"},
    ]
    r = client.post("/v1/responses", json={"model": aliases[2], "input": history, "tools": tools})
    assert r.status_code == 200
    assert seen[1]["input"] == history and seen[1]["tools"] == tools


def test_official_sdk_and_revocation(relay_client):
    from openai import OpenAI

    client, aliases, uid = relay_client
    app.state.upstream_transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json=completion(json.loads(req.content)))
    )
    sdk = OpenAI(api_key="test", base_url="http://testserver/v1", http_client=client, max_retries=0)
    # Supply the actual relay header; SDK must not replace it with its placeholder key.
    headers = {"Authorization": client.headers["Authorization"]}
    result = sdk.responses.create(model=aliases[0], input="read", extra_headers=headers)
    assert result.model == aliases[0] and result.output[0].type == "function_call"
    assert result.usage.output_tokens_details.reasoning_tokens == 6
    second = sdk.responses.create(
        model=aliases[0],
        input=result.output,
        extra_headers=headers,
    )
    assert second.output[1].encrypted_content == "opaque"

    async def revoke():
        async with SessionLocal() as db:
            key = await db.scalar(select(AccessKey).where(AccessKey.user_id == uid))
            key.active = False
            await db.commit()

    client.portal.call(revoke)
    assert (
        client.post(
            "/v1/responses", json={"model": aliases[0], "input": "hi"}, headers=headers
        ).status_code
        == 401
    )


def test_mode_and_foreign_model_rejected(relay_client):
    client, aliases, _ = relay_client

    async def restrict():
        async with SessionLocal() as db:
            route = await db.scalar(select(ModelRoute).where(ModelRoute.public_name == aliases[0]))
            route.api_mode = "chat"
            await db.commit()

    client.portal.call(restrict)
    assert (
        client.post("/v1/responses", json={"model": aliases[0], "input": "hi"}).status_code == 422
    )
    assert (
        client.post("/v1/responses", json={"model": "unassigned", "input": "hi"}).status_code == 404
    )


class EventStream(httpx.AsyncByteStream):
    def __init__(self, chunks, error=None):
        self.chunks, self.error, self.closed = chunks, error, False

    async def __aiter__(self):
        for chunk in self.chunks:
            await asyncio.sleep(0)
            yield chunk
        if self.error:
            raise self.error

    async def aclose(self):
        self.closed = True


def test_named_sse_tools_usage_and_30_concurrent_streams(relay_client):
    client, aliases, _ = relay_client
    streams = []

    def upstream(req):
        body = json.loads(req.content)
        events = [
            {"type": "response.created", "response": {"id": "resp_1", "model": "gpt-6.1-sol"}},
            {
                "type": "response.function_call_arguments.delta",
                "delta": "{}",
                "item_id": "fc_1",
                "output_index": 0,
            },
            {"type": "response.completed", "response": completion(body)},
        ]
        raw = "".join(
            "event: " + e["type"] + "\ndata: " + json.dumps(e) + "\n\n" for e in events
        ).encode()
        stream = EventStream([raw[:17], raw[17:99], raw[99:]])
        streams.append(stream)
        return httpx.Response(200, stream=stream, headers={"content-type": "text/event-stream"})

    app.state.upstream_transport = httpx.MockTransport(upstream)

    def call(i):
        r = client.post(
            "/v1/responses", json={"model": aliases[2], "input": f"isolated-{i}", "stream": True}
        )
        assert r.status_code == 200
        events = [json.loads(s[6:]) for s in r.text.splitlines() if s.startswith("data: ")]
        assert events[-1]["response"]["echo"] == f"isolated-{i}"
        assert events[-1]["response"]["model"] == aliases[2]
        assert "event: response.function_call_arguments.delta" in r.text
        assert "[DONE]" not in r.text and "gpt-6.1-sol" not in r.text

    with ThreadPoolExecutor(max_workers=30) as pool:
        list(pool.map(call, range(30)))
    assert all(s.closed for s in streams)


@pytest.mark.parametrize(
    "failure", ["invalid_json", "failed", "truncated", "timeout", "429", "500", "no_usage"]
)
def test_failure_sanitization_and_settlement(relay_client, failure):
    client, aliases, uid = relay_client

    def upstream(req):
        if failure in {"429", "500"}:
            return httpx.Response(int(failure), text=SECRET)
        if failure == "invalid_json":
            return httpx.Response(200, text=SECRET)
        if failure == "no_usage":
            return httpx.Response(200, json=completion({}, False))
        events = [{"type": "response.created", "response": {"model": "gpt-6.1-sol"}}]
        if failure == "failed":
            events.append({"type": "response.failed", "response": {"error": {"message": SECRET}}})
        raw = "".join("data: " + json.dumps(e) + "\n\n" for e in events).encode()
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=EventStream([raw], httpx.ReadTimeout(SECRET) if failure == "timeout" else None),
        )

    app.state.upstream_transport = httpx.MockTransport(upstream)
    stream = failure in {"failed", "truncated", "timeout"}
    r = client.post("/v1/responses", json={"model": aliases[2], "input": "hi", "stream": stream})
    assert SECRET not in r.text
    if stream:
        assert "event: error" in r.text and "response.completed" not in r.text
    else:
        assert r.status_code == (200 if failure == "no_usage" else 429 if failure == "429" else 502)

    async def check():
        async with SessionLocal() as db:
            row = await db.scalar(select(UsageLedger).where(UsageLedger.user_id == uid))
            assert row is not None
            assert row.output_tokens == (0 if failure in {"429", "500"} else 256)
            if failure == "timeout":
                assert row.status_code == 504

    client.portal.call(check)


@pytest.mark.asyncio
async def test_cancellation_closes_and_settles_once():
    response = httpx.Response(200, stream=EventStream([b'data: {"type":"response.created"}\n\n']))
    counts = []

    async def settle(*args):
        counts.append(args)

    async def close():
        await response.aclose()

    generator = stream_events(response, "responses", "public", SECRET, "req_test", settle, close)
    await generator.__anext__()
    await generator.aclose()
    assert response.is_closed and len(counts) == 1 and counts[0][1] == 499

    class Disconnected:
        async def is_disconnected(self):
            return True

    with pytest.raises(asyncio.CancelledError):
        await while_connected(Disconnected(), asyncio.sleep(60))
