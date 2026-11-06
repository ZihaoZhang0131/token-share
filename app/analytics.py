"""Read-only statistics over the complete, settled usage ledger."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UsageLedger, User
from app.schemas import AnalyticsPeriod

BEIJING = ZoneInfo("Asia/Shanghai")


def period_bounds(period: AnalyticsPeriod, now: Optional[datetime] = None):
    end = now or datetime.now(timezone.utc)
    local = end.astimezone(BEIJING)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "month":
        start = start.replace(day=1)
    else:
        start -= timedelta(days=6 if period == "7d" else 29)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


async def usage_analytics(
    db: AsyncSession,
    period: AnalyticsPeriod = "month",
    user_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> dict:
    start, end = period_bounds(period, now)
    conditions = [UsageLedger.created_at >= start, UsageLedger.created_at < end]
    if user_id is not None:
        conditions.append(UsageLedger.user_id == user_id)

    # Both databases store UTC; group in Beijing before turning the timestamp into a date.
    if db.get_bind().dialect.name == "sqlite":
        day = func.date(UsageLedger.created_at, "+8 hours")
    else:
        day = cast(func.timezone("Asia/Shanghai", UsageLedger.created_at), Date)
    rows = await db.execute(
        select(
            day.label("day"),
            func.count(UsageLedger.id).label("requests"),
            func.sum(UsageLedger.input_tokens).label("input_tokens"),
            func.sum(UsageLedger.output_tokens).label("output_tokens"),
            func.sum(UsageLedger.total_tokens).label("total_tokens"),
            func.sum(case((UsageLedger.status_code < 400, 1), else_=0)).label("successes"),
            func.sum(UsageLedger.latency_ms).label("latency_sum"),
        )
        .where(*conditions)
        .group_by(day)
        .order_by(day)
    )
    counters = ("requests", "input_tokens", "output_tokens", "total_tokens", "successes")
    summary = {key: 0 for key in counters}
    latency_sum = 0
    by_day = {}
    for row in rows.mappings():
        values = {key: int(row[key]) for key in counters}
        for key in counters:
            summary[key] += values[key]
        latency_sum += int(row["latency_sum"])
        values["failures"] = values["requests"] - values["successes"]
        values["avg_latency_ms"] = round(row["latency_sum"] / values["requests"], 1)
        by_day[str(row["day"])] = values

    summary["failures"] = summary["requests"] - summary["successes"]
    summary["success_rate"] = (
        round(summary["successes"] / summary["requests"] * 100, 2) if summary["requests"] else None
    )
    summary["avg_latency_ms"] = (
        round(latency_sum / summary["requests"], 1) if summary["requests"] else None
    )
    daily = []
    cursor = start.astimezone(BEIJING).date()
    while cursor <= end.astimezone(BEIJING).date():
        label = cursor.isoformat()
        values = by_day.get(
            label, {**dict.fromkeys(counters, 0), "failures": 0, "avg_latency_ms": None}
        )
        daily.append({"date": label, **values})
        cursor += timedelta(days=1)

    async def ranking(by_user=False):
        identifier = UsageLedger.user_id if by_user else UsageLedger.model_alias
        label = User.display_name if by_user else UsageLedger.model_alias
        query = select(
            identifier.label("id"),
            label.label("label"),
            func.sum(UsageLedger.total_tokens).label("total_tokens"),
            func.count(UsageLedger.id).label("requests"),
        ).select_from(UsageLedger)
        if by_user:
            query = query.join(User, User.id == UsageLedger.user_id)
        query = (
            query.where(*conditions)
            .group_by(identifier, label)
            .order_by(func.sum(UsageLedger.total_tokens).desc(), identifier)
            .limit(5)
        )
        result = [dict(row) for row in (await db.execute(query)).mappings()]
        remaining_requests = summary["requests"] - sum(row["requests"] for row in result)
        if remaining_requests:
            result.append(
                {
                    "id": "other",
                    "label": "其他",
                    "requests": remaining_requests,
                    "total_tokens": summary["total_tokens"]
                    - sum(row["total_tokens"] for row in result),
                }
            )
        return result

    response = {
        "period": period,
        "start": start,
        "end": end,
        "timezone": "Asia/Shanghai",
        "summary": summary,
        "daily": daily,
        "models": await ranking(),
    }
    if user_id is None:
        response["users"] = await ranking(by_user=True)
    return response
