from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select

from app.config import get_settings
from app.database import SessionLocal
from app.models import MonthlyUsageAggregate, UsageLedger, utcnow

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _month_of(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(SHANGHAI).strftime("%Y%m")


def _oldest_retained_month(now: datetime) -> str:
    local = now.astimezone(SHANGHAI)
    month_index = local.year * 12 + local.month - 1 - 12
    return f"{month_index // 12:04d}{month_index % 12 + 1:02d}"


async def run_retention(batch_size: int = 5000) -> Dict[str, int]:
    """Roll request metadata older than the retention window into 13-month summaries."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.log_retention_days)
    archived = 0

    async with SessionLocal() as db:
        while True:
            rows = list(
                (
                    await db.execute(
                        select(UsageLedger)
                        .where(UsageLedger.created_at < cutoff)
                        .order_by(UsageLedger.created_at)
                        .limit(batch_size)
                    )
                ).scalars()
            )
            if not rows:
                break

            grouped: Dict[Tuple[str, str, str], Dict[str, int]] = defaultdict(
                lambda: {
                    "request_count": 0,
                    "success_count": 0,
                    "error_count": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                }
            )
            for row in rows:
                values = grouped[(_month_of(row.created_at), row.user_id, row.model_alias)]
                values["request_count"] += 1
                values["success_count" if row.status_code < 400 else "error_count"] += 1
                values["input_tokens"] += row.input_tokens
                values["output_tokens"] += row.output_tokens
                values["total_tokens"] += row.total_tokens

            for (month, user_id, model_alias), values in grouped.items():
                aggregate = await db.scalar(
                    select(MonthlyUsageAggregate).where(
                        MonthlyUsageAggregate.month == month,
                        MonthlyUsageAggregate.user_id == user_id,
                        MonthlyUsageAggregate.model_alias == model_alias,
                    )
                )
                if aggregate is None:
                    aggregate = MonthlyUsageAggregate(
                        month=month, user_id=user_id, model_alias=model_alias
                    )
                    db.add(aggregate)
                for field, amount in values.items():
                    setattr(aggregate, field, (getattr(aggregate, field) or 0) + amount)
                aggregate.updated_at = utcnow()

            await db.execute(
                delete(UsageLedger).where(UsageLedger.id.in_([row.id for row in rows]))
            )
            archived += len(rows)
            await db.commit()

        result = await db.execute(
            delete(MonthlyUsageAggregate).where(
                MonthlyUsageAggregate.month < _oldest_retained_month(now)
            )
        )
        aggregates_deleted = int(result.rowcount or 0)
        await db.commit()

    return {"request_logs_archived": archived, "old_aggregates_deleted": aggregates_deleted}
