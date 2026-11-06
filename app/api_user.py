from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import usage_analytics
from app.database import get_db
from app.deps import SessionIdentity, current_session, require_csrf
from app.models import AccessKey, ModelRoute
from app.schemas import (
    AccessKeyCreate,
    AccessKeyCreated,
    AccessKeyView,
    AnalyticsPeriod,
    AnalyticsView,
    ModelView,
    UsageSummary,
    UserView,
)
from app.security import generate_access_key
from app.services import usage_summary, write_audit

router = APIRouter(prefix="/api/me", tags=["user"])


def ensure_ready(identity: SessionIdentity) -> None:
    if identity.user.must_change_password:
        raise HTTPException(status_code=403, detail="请先修改初始密码")


@router.get("", response_model=UserView)
async def me(identity: SessionIdentity = Depends(current_session)):
    return identity.user


@router.get("/usage", response_model=UsageSummary)
async def my_usage(
    identity: SessionIdentity = Depends(current_session), db: AsyncSession = Depends(get_db)
):
    ensure_ready(identity)
    return await usage_summary(db, identity.user)


@router.get("/analytics", response_model=AnalyticsView)
async def my_analytics(
    period: AnalyticsPeriod = "month",
    identity: SessionIdentity = Depends(current_session),
    db: AsyncSession = Depends(get_db),
):
    ensure_ready(identity)
    return await usage_analytics(db, period, user_id=identity.user.id)


@router.get("/models", response_model=list[ModelView])
async def my_models(
    identity: SessionIdentity = Depends(current_session), db: AsyncSession = Depends(get_db)
):
    ensure_ready(identity)
    result = await db.execute(
        select(ModelRoute)
        .where(
            ModelRoute.active.is_(True), ModelRoute.public_name.in_(identity.user.allowed_models)
        )
        .order_by(ModelRoute.public_name)
    )
    return list(result.scalars())


@router.get("/keys", response_model=list[AccessKeyView])
async def list_keys(
    identity: SessionIdentity = Depends(current_session), db: AsyncSession = Depends(get_db)
):
    ensure_ready(identity)
    result = await db.execute(
        select(AccessKey)
        .where(AccessKey.user_id == identity.user.id)
        .order_by(AccessKey.created_at.desc())
    )
    return list(result.scalars())


@router.post("/keys", response_model=AccessKeyCreated, status_code=201)
async def create_key(
    payload: AccessKeyCreate,
    identity: SessionIdentity = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    ensure_ready(identity)
    count = await db.scalar(
        select(func.count(AccessKey.id)).where(
            AccessKey.user_id == identity.user.id, AccessKey.active.is_(True)
        )
    )
    if int(count or 0) >= 5:
        raise HTTPException(status_code=409, detail="每个账号最多保留 5 把有效 Key")
    if payload.rpm_limit > identity.user.rpm_limit:
        raise HTTPException(status_code=422, detail="RPM 不能超过管理员设置的账号上限")
    if payload.tpm_limit > identity.user.tpm_limit:
        raise HTTPException(status_code=422, detail="TPM 不能超过管理员设置的账号上限")
    plaintext, prefix, secret_hash, last4 = generate_access_key()
    key = AccessKey(
        user_id=identity.user.id,
        name=payload.name,
        prefix=prefix,
        secret_hash=secret_hash,
        last4=last4,
        rpm_limit=payload.rpm_limit,
        tpm_limit=payload.tpm_limit,
    )
    db.add(key)
    await db.flush()
    await write_audit(
        db,
        actor_user_id=identity.user.id,
        action="access_key.create",
        target_type="access_key",
        target_id=key.id,
        metadata={"prefix": prefix, "rpm": key.rpm_limit, "tpm": key.tpm_limit},
    )
    await db.commit()
    await db.refresh(key)
    return AccessKeyCreated(key=AccessKeyView.model_validate(key), plaintext=plaintext)


@router.delete("/keys/{key_id}", status_code=204)
async def revoke_key(
    key_id: str,
    identity: SessionIdentity = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    ensure_ready(identity)
    result = await db.execute(
        select(AccessKey).where(AccessKey.id == key_id, AccessKey.user_id == identity.user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="Key 不存在")
    key.active = False
    key.revoked_at = datetime.now(timezone.utc)
    await write_audit(
        db,
        actor_user_id=identity.user.id,
        action="access_key.revoke",
        target_type="access_key",
        target_id=key.id,
        metadata={"prefix": key.prefix},
    )
    await db.commit()
