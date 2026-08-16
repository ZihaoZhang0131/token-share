import json
from datetime import datetime, timedelta, timezone

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.database import SessionLocal
from app.main import app
from app.maintenance import run_retention
from app.models import MonthlyUsageAggregate, Provider, UsageLedger

ADMIN_INITIAL = "InitialAdmin!234"
ADMIN_PASSWORD = "ChangedAdmin!234"
USER_INITIAL = "InitialUser!234"
USER_PASSWORD = "ChangedUser!234"


def login(client: TestClient, email: str, password: str):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def csrf_headers(session):
    return {"X-CSRF-Token": session["csrf_token"]}


def mock_upstream(request: httpx.Request) -> httpx.Response:
    assert request.headers["authorization"] == "Bearer sk-upstream-real-secret"
    if request.url.path.endswith("/models"):
        return httpx.Response(200, json={"object": "list", "data": []})
    body = json.loads(request.content)
    assert body["model"] == "upstream-chat-model"
    if body.get("stream"):
        chunks = [
            {
                "id": "chatcmpl_1",
                "object": "chat.completion.chunk",
                "model": "upstream-chat-model",
                "choices": [{"index": 0, "delta": {"content": "你好"}}],
            },
            {
                "id": "chatcmpl_1",
                "object": "chat.completion.chunk",
                "model": "upstream-chat-model",
                "choices": [],
                "usage": {"prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10},
            },
        ]
        content = "".join(f"data: {json.dumps(item)}\n\n" for item in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, text=content, headers={"content-type": "text/event-stream"})
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl_1",
            "object": "chat.completion",
            "model": "upstream-chat-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "你好"}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10},
        },
    )


def test_full_admin_user_and_proxy_flow():
    with TestClient(app) as client:
        app.state.upstream_transport = httpx.MockTransport(mock_upstream)
        assert client.get("/health/ready").status_code == 200

        admin = login(client, "admin@example.com", ADMIN_INITIAL)
        assert admin["user"]["must_change_password"] is True
        response = client.post(
            "/api/auth/change-password",
            headers=csrf_headers(admin),
            json={"current_password": ADMIN_INITIAL, "new_password": ADMIN_PASSWORD},
        )
        assert response.status_code == 200, response.text
        admin = response.json()

        response = client.post(
            "/api/admin/providers",
            headers=csrf_headers(admin),
            json={
                "name": "Mock Provider",
                "base_url": "https://example.com/v1",
                "api_key": "sk-upstream-real-secret",
                "timeout_seconds": 30,
                "supports_stream_usage": True,
            },
        )
        assert response.status_code == 201, response.text
        provider = response.json()
        assert provider["key_last4"] == "cret"
        assert "sk-upstream" not in response.text

        response = client.post(
            f"/api/admin/providers/{provider['id']}/test", headers=csrf_headers(admin)
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True

        response = client.post(
            "/api/admin/models",
            headers=csrf_headers(admin),
            json={
                "public_name": "public-chat",
                "upstream_model": "upstream-chat-model",
                "provider_id": provider["id"],
                "max_output_tokens": 256,
                "tokenizer": "cl100k_base",
            },
        )
        assert response.status_code == 201, response.text

        response = client.post(
            "/api/admin/users",
            headers=csrf_headers(admin),
            json={
                "email": "user@example.com",
                "display_name": "测试用户",
                "temporary_password": USER_INITIAL,
                "monthly_token_limit": 100000,
                "rpm_limit": 60,
                "tpm_limit": 100000,
                "allowed_models": ["public-chat"],
            },
        )
        assert response.status_code == 201, response.text

        client.post("/api/auth/logout", headers=csrf_headers(admin))
        user = login(client, "user@example.com", USER_INITIAL)
        response = client.post(
            "/api/auth/change-password",
            headers=csrf_headers(user),
            json={"current_password": USER_INITIAL, "new_password": USER_PASSWORD},
        )
        assert response.status_code == 200, response.text
        user = response.json()

        assert (
            client.post(
                "/api/me/keys", json={"name": "bad", "rpm_limit": 10, "tpm_limit": 1000}
            ).status_code
            == 403
        )
        response = client.post(
            "/api/me/keys",
            headers=csrf_headers(user),
            json={"name": "本机", "rpm_limit": 10, "tpm_limit": 10000},
        )
        assert response.status_code == 201, response.text
        relay_key = response.json()["plaintext"]
        assert relay_key.startswith("ts_sk_")
        assert relay_key not in client.get("/api/me/keys").text

        auth = {"Authorization": f"Bearer {relay_key}"}
        response = client.get("/v1/models", headers=auth)
        assert response.status_code == 200
        assert response.json()["data"][0]["id"] == "public-chat"

        response = client.post(
            "/v1/chat/completions",
            headers=auth,
            json={
                "model": "public-chat",
                "messages": [{"role": "user", "content": "你好"}],
                "max_tokens": 16,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["model"] == "public-chat"
        assert "upstream-chat-model" not in response.text
        assert "sk-upstream-real-secret" not in response.text

        with client.stream(
            "POST",
            "/v1/chat/completions",
            headers=auth,
            json={
                "model": "public-chat",
                "messages": [{"role": "user", "content": "你好"}],
                "stream": True,
                "max_tokens": 16,
            },
        ) as response:
            content = "".join(response.iter_text())
        assert response.status_code == 200
        assert '"model": "public-chat"' in content
        assert "upstream-chat-model" not in content
        assert "data: [DONE]" in content

        usage = client.get("/api/me/usage").json()
        assert usage["used_tokens"] == 20
        assert usage["request_count"] == 2


def test_encrypted_provider_value_is_not_plaintext():
    async def check():
        async with SessionLocal() as db:
            provider = await db.scalar(select(Provider).where(Provider.name == "Mock Provider"))
            assert provider is not None
            assert b"sk-upstream-real-secret" not in provider.key_ciphertext

    import asyncio

    asyncio.run(check())


def test_retention_rolls_old_metadata_into_monthly_aggregate():
    async def check():
        async with SessionLocal() as db:
            old = datetime.now(timezone.utc) - timedelta(days=91)
            await db.execute(update(UsageLedger).values(created_at=old))
            await db.commit()

        result = await run_retention()
        assert result["request_logs_archived"] == 2

        async with SessionLocal() as db:
            assert await db.scalar(select(func.count(UsageLedger.id))) == 0
            aggregate = await db.scalar(select(MonthlyUsageAggregate))
            assert aggregate is not None
            assert aggregate.request_count == 2
            assert aggregate.total_tokens == 20

    import asyncio

    asyncio.run(check())
