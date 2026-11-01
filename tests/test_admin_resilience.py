import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import update

from app.database import SessionLocal
from app.main import app
from app.models import Role, User, WebSession
from app.security import hash_password, sha256_text


def test_orm_rejects_reserved_email_and_normalizes_valid_email():
    with pytest.raises(ValidationError):
        User(email="release@internal.invalid")
    user = User(email="Operator@EXAMPLE.COM")
    assert user.email == "operator@example.com"
    with pytest.raises(ValidationError):
        user.email = "release@internal.invalid"
    assert user.email == "operator@example.com"


@pytest.mark.parametrize("active", [True, False])
def test_admin_lists_survive_legacy_email_but_new_input_stays_strict(active):
    with TestClient(app) as client:
        tag = uuid.uuid4().hex
        token, csrf = f"test-session-{tag}", f"test-csrf-{tag}"
        bad_email = f"legacy-{tag}@internal.invalid"

        async def seed():
            async with SessionLocal() as db:
                attrs = dict(
                    password_hash=hash_password("TestAdmin!456789"),
                    must_change_password=False,
                    monthly_token_limit=10000,
                    rpm_limit=10,
                    tpm_limit=10000,
                    allowed_models=[],
                )
                admin = User(
                    email=f"admin-{tag}@example.com",
                    display_name="Regression admin",
                    role=Role.admin,
                    **attrs,
                )
                legacy = User(
                    email=f"legacy-{tag}@example.com",
                    display_name="Legacy fixture",
                    active=active,
                    **attrs,
                )
                db.add_all([admin, legacy])
                await db.flush()
                # Simulate a historical/imported row, bypassing today's ORM validators.
                await db.execute(update(User).where(User.id == legacy.id).values(email=bad_email))
                db.add(
                    WebSession(
                        token_hash=sha256_text(token),
                        csrf_token=csrf,
                        user_id=admin.id,
                        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                    )
                )
                await db.commit()

        client.portal.call(seed)
        client.cookies.set("token_station_session", token)
        for endpoint in ("dashboard", "providers", "models", "users", "logs", "audit"):
            response = client.get(f"/api/admin/{endpoint}")
            assert response.status_code == 200, (endpoint, response.text)
            assert "password_hash" not in response.text and "key_ciphertext" not in response.text
        legacy = next(u for u in client.get("/api/admin/users").json() if u["email"] == bad_email)
        assert legacy["active"] is active
        response = client.post(
            "/api/admin/users",
            headers={"X-CSRF-Token": csrf},
            json={
                "email": "new@internal.invalid",
                "display_name": "Invalid",
                "temporary_password": "TestUser!456789",
                "monthly_token_limit": 1000,
                "rpm_limit": 10,
                "tpm_limit": 1000,
                "allowed_models": [],
            },
        )
        assert response.status_code == 422
