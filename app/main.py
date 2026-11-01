from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from app.api_admin import router as admin_router
from app.api_auth import router as auth_router
from app.api_user import router as user_router
from app.config import get_settings
from app.database import SessionLocal, create_tables
from app.gateway import router as proxy_router
from app.models import Role, User
from app.quotas import QuotaService
from app.security import hash_password, validate_password_strength

settings = get_settings()
alembic_config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
expected_migration = ScriptDirectory.from_config(alembic_config).get_current_head()


async def bootstrap() -> None:
    async with SessionLocal() as db:
        user = await db.scalar(
            select(User).where(User.email == settings.bootstrap_admin_email.lower())
        )
        if not user:
            validate_password_strength(settings.bootstrap_admin_password)
            db.add(
                User(
                    email=settings.bootstrap_admin_email.lower(),
                    display_name="系统管理员",
                    role=Role.admin,
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    must_change_password=True,
                    monthly_token_limit=1,
                    rpm_limit=1,
                    tpm_limit=100,
                    allowed_models=[],
                )
            )
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_tables:
        await create_tables()
    await bootstrap()
    app.state.quota = QuotaService(settings.redis_url)
    yield
    await app.state.quota.close()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def security_and_size_headers(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.max_request_bytes:
                return JSONResponse(status_code=413, content={"detail": "请求体过大"})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "无效的 Content-Length"})
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'",
    )
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/v1/"):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "message": "请求参数不符合当前接口格式",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "validation_error",
                }
            },
        )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


app.include_router(auth_router)
app.include_router(user_router)
app.include_router(admin_router)
app.include_router(proxy_router)


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready(request: Request):
    checks = {"database": False, "redis": False, "migrations": False}
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
            checks["database"] = True
            if settings.auto_create_tables:
                checks["migrations"] = True
            else:
                current_migration = await db.scalar(text("SELECT version_num FROM alembic_version"))
                checks["migrations"] = current_migration == expected_migration
        checks["redis"] = await request.app.state.quota.ping()
    except Exception:
        pass
    status_code = 200 if all(checks.values()) else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if status_code == 200 else "error", "checks": checks},
    )


frontend = settings.frontend_path
if frontend.exists():
    assets = frontend / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        requested = frontend / path
        if path and requested.is_file() and frontend in requested.resolve().parents:
            return FileResponse(requested)
        return FileResponse(frontend / "index.html")
