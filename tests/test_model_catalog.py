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
from app.model_policy import DEEPSEEK_MODEL_EFFORTS, OPENAI_MODEL_EFFORTS
from app.models import ModelRoute, Provider, Role, User
from app.security import encrypt_secret


@pytest.mark.parametrize("vendor", ["openai", "deepseek"])
def test_catalog_transaction_idempotency_and_permissions(tmp_path, monkeypatch, vendor):
    spec = importlib.util.spec_from_file_location(
        f"configure_{vendor}_models",
        Path(__file__).resolve().parents[1] / f"scripts/configure_{vendor}_models.py",
    )
    catalog = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(catalog)
    deepseek = vendor == "deepseek"
    endpoint = "https://api.deepseek.com" if deepseek else "https://api.openai.com/v1"

    async def check():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'catalog.db'}")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(catalog, "SessionLocal", sessions)
        available = list(DEEPSEEK_MODEL_EFFORTS if deepseek else OPENAI_MODEL_EFFORTS)
        real_client = httpx.AsyncClient

        def upstream(request):
            assert str(request.url) == endpoint + "/models"
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
                    name=vendor,
                    base_url=endpoint,
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
                        public_name=available[-1],
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
                if deepseek:
                    db.add(
                        ModelRoute(
                            public_name="deepseek-v4-pro",
                            upstream_model="deepseek-v4-pro",
                            provider_id=pid,
                            api_mode="chat",
                            max_output_tokens=100000,
                        )
                    )
                await db.commit()
            await catalog.configure(pid)
            async with sessions() as db:
                assert await db.scalar(select(func.count()).select_from(ModelRoute)) == int(
                    deepseek
                )
            await catalog.configure(pid, apply=True)
            await catalog.configure(pid, apply=True)
            async with sessions() as db:
                routes = list(await db.scalars(select(ModelRoute)))
                assert len(routes) == (10 if deepseek else 54)
                assert sum(r.api_mode == "responses" for r in routes) == (0 if deepseek else 8)
                if deepseek:
                    base = next(r for r in routes if r.public_name == "deepseek-v4-pro")
                    assert base.max_output_tokens == 100000 and base.api_mode == "both"
                assert (await db.get(User, uid)).allowed_models == ["existing-only"]
                assert (await db.get(User, uid)).password_hash == "fixture"
                for route in routes:
                    if deepseek and route.public_name == "deepseek-v4-pro":
                        continue
                    assert route.max_output_tokens == (393216 if deepseek else 128000)
                    assert route.default_output_tokens is None

            spec = importlib.util.spec_from_file_location(
                "output_budgets", Path(__file__).resolve().parents[1]
                / "scripts/configure_output_budgets.py",
            )
            budgets = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(budgets)
            monkeypatch.setattr(budgets, "SessionLocal", sessions)
            # Simulate migration 0003's conservative backfill.
            async with sessions() as db:
                for route in await db.scalars(select(ModelRoute)):
                    route.default_output_tokens = route.max_output_tokens
                await db.commit()
            assert len(await budgets.configure()) == len(routes)
            async with sessions() as db:
                assert all(r.default_output_tokens is not None
                           for r in await db.scalars(select(ModelRoute)))
            assert len(await budgets.configure(apply=True)) == len(routes)
            assert await budgets.configure(apply=True) == []
            async with sessions() as db:
                assert all(r.default_output_tokens is None
                           and r.max_output_tokens == (393216 if deepseek else 128000)
                           for r in await db.scalars(select(ModelRoute)))
                assert (await db.get(User, uid)).allowed_models == ["existing-only"]
                assert (await db.get(User, uid)).password_hash == "fixture"
            available.pop()
            with pytest.raises(RuntimeError, match="missing models"):
                await catalog.configure(pid, apply=True)
        finally:
            await engine.dispose()

    asyncio.run(check())
