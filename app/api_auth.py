from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import SessionIdentity, current_session, require_csrf
from app.models import User, WebSession
from app.schemas import LoginInput, PasswordChangeInput, SessionView, UserView
from app.security import (
    generate_csrf_token,
    generate_session_token,
    hash_password,
    validate_password_strength,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


@router.post("/login", response_model=SessionView)
async def login(
    payload: LoginInput, request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    ip = request.client.host if request.client else "unknown"
    if not await request.app.state.quota.allow_login(ip):
        raise HTTPException(status_code=429, detail="登录尝试过于频繁")
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if user and user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            raise HTTPException(status_code=423, detail="账号已临时锁定，请稍后重试")
    if not user or not verify_password(payload.password, user.password_hash):
        if user:
            user.login_failures += 1
            if user.login_failures >= 5:
                user.locked_until = now + timedelta(minutes=15)
                user.login_failures = 0
            await db.commit()
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not user.active:
        raise HTTPException(status_code=403, detail="账号已停用")
    user.login_failures = 0
    user.locked_until = None
    token, token_hash = generate_session_token()
    csrf = generate_csrf_token()
    session = WebSession(
        token_hash=token_hash,
        csrf_token=csrf,
        user_id=user.id,
        expires_at=now + timedelta(hours=settings.session_hours),
    )
    db.add(session)
    await db.commit()
    response.set_cookie(
        "token_station_session",
        token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/",
    )
    return SessionView(user=UserView.model_validate(user), csrf_token=csrf)


@router.get("/session", response_model=SessionView)
async def session(identity: SessionIdentity = Depends(current_session)):
    return SessionView(
        user=UserView.model_validate(identity.user), csrf_token=identity.session.csrf_token
    )


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    identity: SessionIdentity = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    await db.delete(identity.session)
    await db.commit()
    response.delete_cookie("token_station_session", path="/")


@router.post("/change-password", response_model=SessionView)
async def change_password(
    payload: PasswordChangeInput,
    identity: SessionIdentity = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, identity.user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码错误")
    try:
        validate_password_strength(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if verify_password(payload.new_password, identity.user.password_hash):
        raise HTTPException(status_code=422, detail="新密码不能与当前密码相同")
    identity.user.password_hash = hash_password(payload.new_password)
    identity.user.must_change_password = False
    await db.execute(
        delete(WebSession).where(
            WebSession.user_id == identity.user.id, WebSession.id != identity.session.id
        )
    )
    await db.commit()
    return SessionView(
        user=UserView.model_validate(identity.user), csrf_token=identity.session.csrf_token
    )
