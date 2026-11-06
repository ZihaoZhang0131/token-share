"""Run inside API container via stdin. Dry-run by default; never edits user grants.

Pass this file on stdin to: docker compose exec -T api python - --provider-id UUID [--apply]
"""

import argparse
import asyncio
import json

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.model_policy import OPENAI_MODEL_EFFORTS, validate_route
from app.models import ModelRoute, Provider, Role, User
from app.security import decrypt_secret
from app.services import write_audit


async def configure(provider_id, apply=False):
    async with SessionLocal() as db:
        provider = await db.get(Provider, provider_id)
        if (
            not provider
            or not provider.active
            or provider.base_url.rstrip("/") != "https://api.openai.com/v1"
        ):
            raise RuntimeError("Expected an active official OpenAI provider")
        secret = decrypt_secret(
            provider.key_ciphertext, provider.key_nonce, provider.key_version, get_settings()
        )
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            response = await client.get(
                provider.base_url.rstrip("/") + "/models",
                headers={"Authorization": "Bearer " + secret},
            )
        if response.status_code != 200:
            raise RuntimeError(f"Model discovery failed: HTTP {response.status_code}")
        available = {item["id"] for item in response.json()["data"]}
        missing = sorted(set(OPENAI_MODEL_EFFORTS) - available)
        if missing:
            raise RuntimeError(f"Account is missing models: {missing}; no changes applied")
        created, preserved, updated = [], [], []
        for model, efforts in OPENAI_MODEL_EFFORTS.items():
            for effort in (None, *efforts):
                alias = model if effort is None else f"{model}-{effort}"
                mode = "responses" if effort == "max" else "both"
                validate_route(model, effort)
                existing = await db.scalar(
                    select(ModelRoute).where(ModelRoute.public_name == alias)
                )
                if existing:
                    if (
                        existing.provider_id,
                        existing.upstream_model,
                        existing.reasoning_effort,
                        existing.active,
                    ) != (provider.id, model, effort, True):
                        raise RuntimeError(
                            f"Conflicting existing route: {alias}; no changes applied"
                        )
                    if existing.api_mode == mode:
                        preserved.append(alias)
                    elif effort == "max" and existing.api_mode == "both":
                        existing.api_mode = mode
                        updated.append(alias)
                    else:
                        raise RuntimeError(f"Conflicting route mode: {alias}; no changes applied")
                    continue
                db.add(
                    ModelRoute(
                        public_name=alias,
                        upstream_model=model,
                        provider_id=provider.id,
                        reasoning_effort=effort,
                        api_mode=mode,
                        active=True,
                        max_output_tokens=128000,
                        default_output_tokens=None,
                        tokenizer="cl100k_base",
                    )
                )
                created.append(alias)
        if apply and (created or updated):
            actor = await db.scalar(
                select(User)
                .where(User.role == Role.admin, User.active.is_(True))
                .order_by(User.created_at)
            )
            if not actor:
                raise RuntimeError("No active administrator")
            await write_audit(
                db,
                actor_user_id=actor.id,
                action="models.catalog.configure",
                target_type="provider",
                target_id=provider.id,
                metadata={
                    "source": "operator-authorized configuration",
                    "created": created,
                    "updated_max_to_responses": updated,
                    "user_permissions_changed": False,
                },
            )
            await db.commit()
        else:
            await db.rollback()
        print(
            json.dumps(
                {
                    "applied": apply,
                    "created": created,
                    "updated_max_to_responses": updated,
                    "preserved": preserved,
                    "user_permissions_changed": False,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider-id", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(configure(args.provider_id, args.apply))
