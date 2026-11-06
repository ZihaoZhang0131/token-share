from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analytics import period_bounds, usage_analytics
from app.api_admin import router as admin_router
from app.api_user import router as user_router
from app.database import Base, get_db
from app.models import AccessKey, Role, UsageLedger, User, WebSession
from app.security import sha256_text

NOW = datetime(2026, 11, 6, 7, 0, tzinfo=timezone.utc)


@pytest.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'analytics.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def account(db, role=Role.user, must_change=False):
    tag = uuid4().hex
    user = User(
        email=f"{tag}@example.com",
        display_name=f"用户 {tag[:6]}",
        role=role,
        password_hash="unused",
        must_change_password=must_change,
        monthly_token_limit=1_000_000,
        rpm_limit=100,
        tpm_limit=100_000,
        allowed_models=[],
    )
    db.add(user)
    await db.flush()
    key = AccessKey(
        user_id=user.id,
        name="test",
        prefix=tag[:8],
        secret_hash=tag,
        last4=tag[-4:],
        rpm_limit=100,
        tpm_limit=100_000,
    )
    db.add(key)
    cookie = f"test-{tag}"
    db.add(
        WebSession(
            user_id=user.id,
            token_hash=sha256_text(cookie),
            csrf_token=tag,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    await db.flush()
    return user, key, cookie


def record(
    user, key, *, at=NOW - timedelta(minutes=1), model="model-a", status=200, tokens=30, latency=100
):
    return UsageLedger(
        request_id=uuid4().hex,
        user_id=user.id,
        access_key_id=key.id,
        model_alias=model,
        input_tokens=tokens // 3,
        output_tokens=tokens - tokens // 3,
        total_tokens=tokens,
        status_code=status,
        latency_ms=latency,
        created_at=at,
    )


@pytest.mark.parametrize(
    "period,now,expected,days",
    [
        ("month", NOW, "2026-10-31T16:00:00+00:00", 6),
        ("7d", NOW, "2026-10-30T16:00:00+00:00", 7),
        ("30d", NOW, "2026-10-07T16:00:00+00:00", 30),
        ("7d", datetime(2027, 1, 1, 0, tzinfo=timezone.utc), "2026-12-25T16:00:00+00:00", 7),
        ("month", datetime(2028, 2, 29, 16, tzinfo=timezone.utc), "2028-02-29T16:00:00+00:00", 1),
    ],
)
async def test_empty_ranges_and_beijing_calendar(sessions, period, now, expected, days):
    start, end = period_bounds(period, now)
    assert start.isoformat() == expected
    assert end == now
    async with sessions() as db:
        data = await usage_analytics(db, period, now=now)
    assert len(data["daily"]) == days
    assert data["summary"]["requests"] == 0
    assert data["summary"]["success_rate"] is None
    assert data["summary"]["avg_latency_ms"] is None
    assert all(row["total_tokens"] == 0 for row in data["daily"])
    assert data["models"] == data["users"] == []


async def test_complete_ledger_aggregates_and_boundary_filtering(sessions):
    start, _ = period_bounds("month", NOW)
    async with sessions() as db:
        user, key, _ = await account(db)
        # More than the UI's old 200-row log limit, split across days and statuses.
        db.add_all([record(user, key, at=start, model="first", tokens=30) for _ in range(205)])
        db.add(
            record(
                user,
                key,
                at=start + timedelta(days=1),
                model="second",
                status=502,
                tokens=60,
                latency=400,
            )
        )
        db.add(record(user, key, at=start - timedelta(microseconds=1), tokens=99999))
        db.add(record(user, key, at=NOW, tokens=99999))
        db.add(record(user, key, at=NOW + timedelta(seconds=1), tokens=99999))
        await db.commit()
        data = await usage_analytics(db, now=NOW)
    summary = data["summary"]
    assert summary == {
        "requests": 206,
        "input_tokens": 2070,
        "output_tokens": 4140,
        "total_tokens": 6210,
        "successes": 205,
        "failures": 1,
        "success_rate": 99.51,
        "avg_latency_ms": 101.5,
    }
    assert data["daily"][0]["date"] == "2026-11-01"
    assert data["daily"][0]["requests"] == 205
    assert data["daily"][1]["failures"] == 1
    assert data["daily"][1]["avg_latency_ms"] == 400
    assert data["daily"][2]["avg_latency_ms"] is None
    assert sum(day["total_tokens"] for day in data["daily"]) == summary["total_tokens"]
    assert sum(item["total_tokens"] for item in data["models"]) == summary["total_tokens"]


async def test_top_five_other_and_user_isolation(sessions):
    async with sessions() as db:
        people = [await account(db) for _ in range(7)]
        for index, (user, key, _) in enumerate(people):
            db.add(record(user, key, model=f"model-{index}", tokens=(index + 1) * 30))
        await db.commit()
        admin = await usage_analytics(db, "7d", now=NOW)
        personal = await usage_analytics(db, "7d", user_id=people[0][0].id, now=NOW)
    for field in ("models", "users"):
        assert len(admin[field]) == 6
        assert admin[field][-1] == {
            "id": "other",
            "label": "其他",
            "total_tokens": 90,
            "requests": 2,
        }
        assert sum(item["total_tokens"] for item in admin[field]) == 840
    assert admin["models"][0]["id"] == "model-6"
    assert personal["summary"]["requests"] == 1
    assert personal["summary"]["total_tokens"] == 30
    assert personal["models"][0]["id"] == "model-0"
    assert "users" not in personal


async def test_analytics_endpoints_permissions_and_contract(sessions, monkeypatch):
    real_bounds = period_bounds
    monkeypatch.setattr(
        "app.analytics.period_bounds",
        lambda period, now=None: real_bounds(
            period,
            NOW,
        ),
    )
    async with sessions() as db:
        admin, admin_key, admin_cookie = await account(db, Role.admin)
        user, key, user_cookie = await account(db)
        _, _, gated_cookie = await account(db, must_change=True)
        db.add(record(admin, admin_key, tokens=90))
        db.add(record(user, key, tokens=30))
        await db.commit()

    async def test_db():
        async with sessions() as db:
            yield db

    app = FastAPI()
    app.include_router(admin_router)
    app.include_router(user_router)
    app.dependency_overrides[get_db] = test_db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/api/me/analytics")).status_code == 401
        assert (await client.get("/api/admin/analytics")).status_code == 401
        client.cookies.set("token_station_session", gated_cookie)
        assert (await client.get("/api/me/analytics")).status_code == 403
        client.cookies.set("token_station_session", user_cookie)
        assert (await client.get("/api/admin/analytics")).status_code == 403
        assert (await client.get("/api/me/analytics?period=all")).status_code == 422
        data = (await client.get("/api/me/analytics")).json()
        assert data["period"] == "month"
        assert data["timezone"] == "Asia/Shanghai"
        assert data["summary"]["total_tokens"] == 30
        assert "users" not in data
        client.cookies.set("token_station_session", admin_cookie)
        data = (await client.get("/api/admin/analytics?period=30d")).json()
        assert data["summary"]["total_tokens"] == 120
        assert len(data["daily"]) == 30
        assert len(data["users"]) == 2
