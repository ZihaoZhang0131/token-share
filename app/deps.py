from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import AccessKey, Role, User, WebSession
from app.security import access_key_prefix, is_expired, sha256_text


@dataclass
class SessionIdentity:
    user: User
    session: WebSession


@dataclass
class APIIdentity:
    user: User
    access_key: AccessKey


async def current_session(request: Request, db: AsyncSession = Depends(get_db)) -> SessionIdentity:
    token = request.cookies.get("token_station_session")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    token_hash = sha256_text(token)
    result = await db.execute(
        select(WebSession)
        .options(selectinload(WebSession.user))
        .where(WebSession.token_hash == token_hash)
    )
    session = result.scalar_one_or_none()
    if not session or is_expired(session.expires_at) or not session.user.active:
        if session:
            await db.delete(session)
            await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")
    return SessionIdentity(session.user, session)


async def require_csrf(
    identity: SessionIdentity = Depends(current_session),
    x_csrf_token: Optional[str] = Header(default=None),
) -> SessionIdentity:
    if not x_csrf_token or not hmac.compare_digest(x_csrf_token, identity.session.csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF 校验失败")
    return identity


async def require_admin(identity: SessionIdentity = Depends(current_session)) -> SessionIdentity:
    if identity.user.role != Role.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    if identity.user.must_change_password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请先修改初始密码")
    return identity


async def require_admin_csrf(identity: SessionIdentity = Depends(require_csrf)) -> SessionIdentity:
    if identity.user.role != Role.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    if identity.user.must_change_password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请先修改初始密码")
    return identity


async def api_identity(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> APIIdentity:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Bearer Token")
    plaintext = authorization[7:].strip()
    try:
        prefix = access_key_prefix(plaintext)
    except ValueError:
        raise HTTPException(status_code=401, detail="无效的访问 Key") from None
    result = await db.execute(
        select(AccessKey).options(selectinload(AccessKey.user)).where(AccessKey.prefix == prefix)
    )
    key = result.scalar_one_or_none()
    if (
        not key
        or not key.active
        or not key.user.active
        or not hmac.compare_digest(key.secret_hash, sha256_text(plaintext))
    ):
        raise HTTPException(status_code=401, detail="无效或已撤销的访问 Key")
    key.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    return APIIdentity(key.user, key)
