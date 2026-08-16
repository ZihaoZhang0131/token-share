from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, UsageLedger, User


def month_bounds() -> Tuple[datetime, datetime, str]:
    local_now = datetime.now(ZoneInfo("Asia/Shanghai"))
    local_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if local_start.month == 12:
        local_end = local_start.replace(year=local_start.year + 1, month=1)
    else:
        local_end = local_start.replace(month=local_start.month + 1)
    return (
        local_start.astimezone(timezone.utc),
        local_end.astimezone(timezone.utc),
        local_start.strftime("%Y-%m"),
    )


async def monthly_usage(db: AsyncSession, user_id: str) -> Dict[str, int]:
    start, end, _ = month_bounds()
    result = await db.execute(
        select(
            func.coalesce(func.sum(UsageLedger.input_tokens), 0),
            func.coalesce(func.sum(UsageLedger.output_tokens), 0),
            func.coalesce(func.sum(UsageLedger.total_tokens), 0),
            func.count(UsageLedger.id),
        ).where(
            UsageLedger.user_id == user_id,
            UsageLedger.created_at >= start,
            UsageLedger.created_at < end,
        )
    )
    input_tokens, output_tokens, total_tokens, count = result.one()
    return {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "total_tokens": int(total_tokens),
        "request_count": int(count),
    }


async def usage_summary(db: AsyncSession, user: User) -> Dict[str, Any]:
    start, end, month = month_bounds()
    totals = await monthly_usage(db, user.id)
    rows = await db.execute(
        select(UsageLedger.created_at, UsageLedger.total_tokens).where(
            UsageLedger.user_id == user.id,
            UsageLedger.created_at >= start,
            UsageLedger.created_at < end,
        )
    )
    by_day: Dict[str, int] = {}
    tz = ZoneInfo("Asia/Shanghai")
    for created_at, total in rows:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        day = created_at.astimezone(tz).strftime("%m-%d")
        by_day[day] = by_day.get(day, 0) + total
    cursor = start.astimezone(tz)
    daily = []
    while cursor < end.astimezone(tz):
        label = cursor.strftime("%m-%d")
        daily.append({"date": label, "tokens": by_day.get(label, 0)})
        cursor += timedelta(days=1)
    return {
        "month": month,
        "used_tokens": totals["total_tokens"],
        "remaining_tokens": max(0, user.monthly_token_limit - totals["total_tokens"]),
        "monthly_token_limit": user.monthly_token_limit,
        "request_count": totals["request_count"],
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "daily": daily,
    }


async def write_audit(
    db: AsyncSession,
    *,
    actor_user_id: str,
    action: str,
    target_type: str,
    target_id: str,
    metadata: Optional[dict] = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=metadata or {},
        )
    )


def estimate_tokens(value: Any, tokenizer_name: str = "cl100k_base") -> int:
    text = (
        value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    )
    try:
        import tiktoken

        tokenizer = tiktoken.get_encoding(tokenizer_name)
        return max(1, len(tokenizer.encode(text)))
    except Exception:
        return max(1, math.ceil(len(text) / 4))


def upstream_client(app, timeout_seconds: int) -> httpx.AsyncClient:
    transport = getattr(app.state, "upstream_transport", None)
    return httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(timeout_seconds, connect=min(10, timeout_seconds)),
        follow_redirects=False,
    )
