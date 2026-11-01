import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import Base
from app.model_policy import OPENAI_MODEL_EFFORTS
from app.models import ModelRoute, Provider, Role, User
from app.security import encrypt_secret

spec = importlib.util.spec_from_file_location(
    "configure_openai_models",
    Path(__file__).resolve().parents[1] / "scripts/configure_openai_models.py",
)
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


def test_catalog_transaction_idempotency_and_permissions(tmp_path, monkeypatch):
    async def check():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'catalog.db'}")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(catalog, "SessionLocal", sessions)
        available = list(OPENAI_MODEL_EFFORTS)
        real_client = httpx.AsyncClient

        def upstream(request):
            assert str(request.url) == "https://api.openai.com/v1/models"
            assert request.headers["authorization"] == "Bearer fixture-secret"
            return httpx.Response(200, json={"data": [{"id": m} for m in available]})

        monkeypatch.setattr(
            catalog,
            "httpx",
            SimpleNamespace(
                AsyncClient=lambda **kwargs: real_client(
                    transport=httpx.MockTransport(upstream), **kwargs
                )
            ),
        )
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with sessions() as db:
                secret = encrypt_secret("fixture-secret", get_settings())
                provider = Provider(
                    name="OpenAI",
                    base_url="https://api.openai.com/v1",
                    key_ciphertext=secret.ciphertext,
                    key_nonce=secret.nonce,
                    key_version=secret.version,
                    key_last4=secret.last4,
                )
                admin = User(
                    email="catalog@example.com",
                    display_name="test",
                    role=Role.admin,
                    password_hash="fixture",
                    monthly_token_limit=1000,
                    rpm_limit=10,
                    tpm_limit=1000,
                    allowed_models=["existing-only"],
                )
                db.add_all([provider, admin])
                await db.flush()
                db.add(
                    ModelRoute(
                        public_name="gpt-5.6-sol",
                        upstream_model="different",
                        provider_id=provider.id,
                    )
                )
                await db.commit()
                pid, uid = provider.id, admin.id
            with pytest.raises(RuntimeError, match="Conflicting"):
                await catalog.configure(pid, apply=True)
            async with sessions() as db:
                assert await db.scalar(select(func.count()).select_from(ModelRoute)) == 1
                await db.execute(delete(ModelRoute))
                await db.commit()
            await catalog.configure(pid)
            async with sessions() as db:
                assert await db.scalar(select(func.count()).select_from(ModelRoute)) == 0
            await catalog.configure(pid, apply=True)
            await catalog.configure(pid, apply=True)
            async with sessions() as db:
                routes = list(await db.scalars(select(ModelRoute)))
                assert len(routes) == 54
                assert sum(r.api_mode == "responses" for r in routes) == 8
                assert (await db.get(User, uid)).allowed_models == ["existing-only"]
                assert (await db.get(User, uid)).password_hash == "fixture"
            available.pop()
            with pytest.raises(RuntimeError, match="missing models"):
                await catalog.configure(pid, apply=True)
        finally:
            await engine.dispose()

    asyncio.run(check())
