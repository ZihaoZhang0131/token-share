"""Set official route ceilings and automatic defaults. Preview unless --apply.

Run via stdin in the API container after migration 0003. Does not edit grants,
credentials, user quotas, or unknown/custom provider routes.
"""

import argparse
import asyncio
import json

from sqlalchemy import select

from app.database import SessionLocal
from app.model_policy import DEEPSEEK_MODEL_EFFORTS, model_family, official_output_limit
from app.models import ModelRoute, Provider, Role, User
from app.services import write_audit


async def configure(apply=False):
    async with SessionLocal() as db:
        changes = []
        rows = await db.execute(select(ModelRoute, Provider).join(ModelRoute.provider))
        for route, provider in rows:
            url = provider.base_url.rstrip("/")
            official_provider = (
                model_family(route.upstream_model) and url == "https://api.openai.com/v1"
            ) or (
                route.upstream_model in DEEPSEEK_MODEL_EFFORTS
                and url in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}
            )
            if not official_provider:
                continue
            maximum = official_output_limit(route.upstream_model)
            if route.max_output_tokens == maximum and route.default_output_tokens is None:
                continue
            changes.append({
                "id": route.id,
                "model": route.public_name,
                "before": [route.max_output_tokens, route.default_output_tokens],
                "after": [maximum, None],
            })
            route.max_output_tokens = maximum
            route.default_output_tokens = None
        if apply and changes:
            actor = await db.scalar(
                select(User).where(User.role == Role.admin, User.active.is_(True))
                .order_by(User.created_at)
            )
            if not actor:
                raise RuntimeError("No active administrator")
            await write_audit(
                db, actor_user_id=actor.id, action="models.output_budgets.configure",
                target_type="model", target_id="catalog", metadata={"changes": changes},
            )
            await db.commit()
        else:
            await db.rollback()
        print(json.dumps({"applied": apply, "changes": changes}, ensure_ascii=False))
        return changes


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    asyncio.run(configure(parser.parse_args().apply))
