from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import SessionIdentity, require_admin, require_admin_csrf
from app.models import AuditLog, ModelRoute, Provider, Role, UsageLedger, User, WebSession
from app.schemas import (
    AdminUserCreate,
    AdminUserUpdate,
    AuditView,
    ModelCreate,
    ModelUpdate,
    ModelView,
    PasswordResetInput,
    ProviderCreate,
    ProviderUpdate,
    ProviderView,
    UsageLogView,
    UserView,
)
from app.security import (
    decrypt_secret,
    encrypt_secret,
    hash_password,
    validate_password_strength,
    validate_upstream_url,
)
from app.services import upstream_client, write_audit

router = APIRouter(prefix="/api/admin", tags=["admin"])
settings = get_settings()


async def ensure_model_aliases(db: AsyncSession, aliases: list[str]) -> None:
    if not aliases:
        return
    result = await db.execute(
        select(ModelRoute.public_name).where(ModelRoute.public_name.in_(aliases))
    )
    found = set(result.scalars())
    missing = sorted(set(aliases) - found)
    if missing:
        raise HTTPException(status_code=422, detail=f"模型不存在：{', '.join(missing)}")


@router.get("/dashboard")
async def dashboard(
    _: SessionIdentity = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    since = datetime.now(timezone.utc) - timedelta(days=30)
    result = await db.execute(
        select(
            func.count(UsageLedger.id),
            func.coalesce(func.sum(UsageLedger.total_tokens), 0),
            func.coalesce(func.avg(UsageLedger.latency_ms), 0),
            func.coalesce(func.sum(case((UsageLedger.status_code < 400, 1), else_=0)), 0),
        ).where(UsageLedger.created_at >= since)
    )
    requests, tokens, avg_latency, successes = result.one()
    user_count = await db.scalar(select(func.count(User.id)).where(User.role == Role.user))
    provider_count = await db.scalar(
        select(func.count(Provider.id)).where(Provider.active.is_(True))
    )
    model_count = await db.scalar(
        select(func.count(ModelRoute.id)).where(ModelRoute.active.is_(True))
    )
    return {
        "period_days": 30,
        "requests": int(requests),
        "tokens": int(tokens),
        "success_rate": round((int(successes) / int(requests) * 100), 2) if requests else 100,
        "avg_latency_ms": round(float(avg_latency), 1),
        "users": int(user_count or 0),
        "providers": int(provider_count or 0),
        "models": int(model_count or 0),
    }


@router.get("/users", response_model=list[UserView])
async def list_users(
    _: SessionIdentity = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars())


@router.post("/users", response_model=UserView, status_code=201)
async def create_user(
    payload: AdminUserCreate,
    identity: SessionIdentity = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
):
    try:
        validate_password_strength(payload.temporary_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await ensure_model_aliases(db, payload.allowed_models)
    exists = await db.scalar(select(User.id).where(User.email == payload.email.lower()))
    if exists:
        raise HTTPException(status_code=409, detail="邮箱已存在")
    user = User(
        email=payload.email.lower(),
        display_name=payload.display_name,
        role=Role.user,
        password_hash=hash_password(payload.temporary_password),
        must_change_password=True,
        monthly_token_limit=payload.monthly_token_limit,
        rpm_limit=payload.rpm_limit,
        tpm_limit=payload.tpm_limit,
        allowed_models=sorted(set(payload.allowed_models)),
    )
    db.add(user)
    await db.flush()
    await write_audit(
        db,
        actor_user_id=identity.user.id,
        action="user.create",
        target_type="user",
        target_id=user.id,
        metadata={
            "email": user.email,
            "monthly_token_limit": user.monthly_token_limit,
            "rpm_limit": user.rpm_limit,
            "tpm_limit": user.tpm_limit,
        },
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserView)
async def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    identity: SessionIdentity = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user or user.role != Role.user:
        raise HTTPException(status_code=404, detail="用户不存在")
    changes = payload.model_dump(exclude_unset=True)
    if "allowed_models" in changes:
        await ensure_model_aliases(db, changes["allowed_models"])
        changes["allowed_models"] = sorted(set(changes["allowed_models"]))
    for key, value in changes.items():
        setattr(user, key, value)
    if changes.get("active") is False:
        await db.execute(delete(WebSession).where(WebSession.user_id == user.id))
    await write_audit(
        db,
        actor_user_id=identity.user.id,
        action="user.update",
        target_type="user",
        target_id=user.id,
        metadata={"fields": sorted(changes)},
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password", status_code=204)
async def reset_password(
    user_id: str,
    payload: PasswordResetInput,
    identity: SessionIdentity = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user or user.role != Role.user:
        raise HTTPException(status_code=404, detail="用户不存在")
    try:
        validate_password_strength(payload.temporary_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user.password_hash = hash_password(payload.temporary_password)
    user.must_change_password = True
    await db.execute(delete(WebSession).where(WebSession.user_id == user.id))
    await write_audit(
        db,
        actor_user_id=identity.user.id,
        action="user.reset_password",
        target_type="user",
        target_id=user.id,
    )
    await db.commit()


@router.get("/providers", response_model=list[ProviderView])
async def list_providers(
    _: SessionIdentity = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Provider).order_by(Provider.created_at.desc()))
    return list(result.scalars())


@router.post("/providers", response_model=ProviderView, status_code=201)
async def create_provider(
    payload: ProviderCreate,
    identity: SessionIdentity = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
):
    try:
        base_url = await validate_upstream_url(payload.base_url, settings.allow_private_upstreams)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    encrypted = encrypt_secret(payload.api_key, settings)
    provider = Provider(
        name=payload.name,
        base_url=base_url,
        key_ciphertext=encrypted.ciphertext,
        key_nonce=encrypted.nonce,
        key_last4=encrypted.last4,
        key_version=encrypted.version,
        timeout_seconds=payload.timeout_seconds,
        supports_stream_usage=payload.supports_stream_usage,
    )
    db.add(provider)
    try:
        await db.flush()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="上游名称已存在") from None
    await write_audit(
        db,
        actor_user_id=identity.user.id,
        action="provider.create",
        target_type="provider",
        target_id=provider.id,
        metadata={"name": provider.name, "base_url": provider.base_url},
    )
    await db.commit()
    await db.refresh(provider)
    return provider


@router.patch("/providers/{provider_id}", response_model=ProviderView)
async def update_provider(
    provider_id: str,
    payload: ProviderUpdate,
    identity: SessionIdentity = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
):
    provider = await db.get(Provider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="上游不存在")
    changes = payload.model_dump(exclude_unset=True)
    if "base_url" in changes:
        try:
            changes["base_url"] = await validate_upstream_url(
                changes["base_url"], settings.allow_private_upstreams
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    api_key = changes.pop("api_key", None)
    if api_key:
        encrypted = encrypt_secret(api_key, settings)
        provider.key_ciphertext = encrypted.ciphertext
        provider.key_nonce = encrypted.nonce
        provider.key_last4 = encrypted.last4
        provider.key_version = encrypted.version
    for key, value in changes.items():
        setattr(provider, key, value)
    await write_audit(
        db,
        actor_user_id=identity.user.id,
        action="provider.update",
        target_type="provider",
        target_id=provider.id,
        metadata={"fields": sorted(changes) + (["api_key"] if api_key else [])},
    )
    await db.commit()
    await db.refresh(provider)
    return provider


@router.post("/providers/{provider_id}/test")
async def test_provider(
    provider_id: str,
    request: Request,
    _: SessionIdentity = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
):
    provider = await db.get(Provider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="上游不存在")
    try:
        await validate_upstream_url(provider.base_url, settings.allow_private_upstreams)
        api_key = decrypt_secret(
            provider.key_ciphertext, provider.key_nonce, provider.key_version, settings
        )
        async with upstream_client(request.app, min(provider.timeout_seconds, 30)) as client:
            response = await client.get(
                f"{provider.base_url}/models",
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            )
        if response.status_code >= 400:
            return {"ok": False, "status": response.status_code, "message": "上游拒绝了连接测试"}
        return {"ok": True, "status": response.status_code, "message": "连接成功"}
    except (httpx.HTTPError, ValueError):
        return {"ok": False, "status": None, "message": "无法连接上游，请检查地址、网络和 Key"}


@router.get("/models", response_model=list[ModelView])
async def list_models(
    _: SessionIdentity = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ModelRoute).order_by(ModelRoute.public_name))
    return list(result.scalars())


@router.post("/models", response_model=ModelView, status_code=201)
async def create_model(
    payload: ModelCreate,
    identity: SessionIdentity = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
):
    provider = await db.get(Provider, payload.provider_id)
    if not provider:
        raise HTTPException(status_code=422, detail="上游不存在")
    route = ModelRoute(**payload.model_dump())
    db.add(route)
    try:
        await db.flush()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="公开模型名已存在") from None
    await write_audit(
        db,
        actor_user_id=identity.user.id,
        action="model.create",
        target_type="model",
        target_id=route.id,
        metadata={"public_name": route.public_name, "provider_id": route.provider_id},
    )
    await db.commit()
    await db.refresh(route)
    return route


@router.patch("/models/{model_id}", response_model=ModelView)
async def update_model(
    model_id: str,
    payload: ModelUpdate,
    identity: SessionIdentity = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
):
    route = await db.get(ModelRoute, model_id)
    if not route:
        raise HTTPException(status_code=404, detail="模型不存在")
    changes = payload.model_dump(exclude_unset=True)
    if "provider_id" in changes and not await db.get(Provider, changes["provider_id"]):
        raise HTTPException(status_code=422, detail="上游不存在")
    for key, value in changes.items():
        setattr(route, key, value)
    await write_audit(
        db,
        actor_user_id=identity.user.id,
        action="model.update",
        target_type="model",
        target_id=route.id,
        metadata={"fields": sorted(changes)},
    )
    await db.commit()
    await db.refresh(route)
    return route


@router.get("/logs", response_model=list[UsageLogView])
async def usage_logs(
    _: SessionIdentity = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = None,
    model: Optional[str] = None,
    status_code: Optional[int] = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    query = select(UsageLedger).order_by(UsageLedger.created_at.desc()).limit(limit)
    if user_id:
        query = query.where(UsageLedger.user_id == user_id)
    if model:
        query = query.where(UsageLedger.model_alias == model)
    if status_code:
        query = query.where(UsageLedger.status_code == status_code)
    result = await db.execute(query)
    return list(result.scalars())


@router.get("/audit", response_model=list[AuditView])
async def audit_logs(
    _: SessionIdentity = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
):
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    return list(result.scalars())
