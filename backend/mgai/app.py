import json
import logging
import secrets
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .config import Settings
from .database import Database
from .jobs import cancel, public_job, submit
from .models import (
    AuditEvent,
    Control,
    Invitation,
    Job,
    Model,
    Session,
    User,
    Workspace,
    now,
    uid,
)
from .providers import NvidiaProvider, ProviderError
from .registry import DEFAULT_MODEL_ID, list_models, seed
from .schemas import (
    CreditGrant,
    Generate,
    Invite,
    Login,
    ModelUpdate,
    PasswordChange,
    Register,
    UserUpdate,
    WorkspaceCreate,
)
from .security import (
    PASSWORDS,
    audit,
    check_origin,
    digest,
    email,
    hash_password,
    limit,
    new_session,
    principal,
    verify_password,
)

logger = logging.getLogger("mgai.api")


def user_view(user):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "active": user.active,
        "credits": user.credits,
        "daily_request_limit": user.daily_request_limit,
        "daily_token_limit": user.daily_token_limit,
    }


def model_view(model):
    return {
        "id": model.id,
        "is_default": model.id == DEFAULT_MODEL_ID,
        "name": model.name,
        "provider": model.provider,
        "license_name": model.license_name,
        "license_url": model.license_url,
        "capabilities": ["text", "chat"],
        "enabled": model.enabled,
        "access_verified": model.access_verified,
        "catalog_present": model.catalog_present,
        "checked_at": model.checked_at,
        "commercial_approved": model.commercial_approved,
        "price_input": str(model.price_input)
        if model.price_input is not None
        else None,
        "price_output": str(model.price_output)
        if model.price_output is not None
        else None,
        "pricing_reference": model.pricing_reference,
    }


def usage_view(session, user=None):
    query = select(Job).where(Job.created_at > now() - timedelta(days=1))
    if user:
        query = query.where(Job.user_id == user.id)
    # Select only aggregates, never decrypt other tenants' content.
    sub = query.subquery()
    row = session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(sub.c.budget_tokens), 0),
            func.coalesce(func.sum(sub.c.prompt_tokens), 0),
            func.coalesce(func.sum(sub.c.completion_tokens), 0),
            func.coalesce(func.sum(sub.c.cost_usd), 0),
            func.count().filter(sub.c.cost_usd.is_(None)),
        ).select_from(sub)
    ).one()
    return {
        "requests_24h": row[0],
        "accounted_tokens_24h": row[1],
        "reported_prompt_tokens": row[2],
        "reported_completion_tokens": row[3],
        "known_cost_usd": str(row[4]),
        "unverified_cost_jobs": row[5],
        "credits": user.credits if user else None,
        "daily_request_limit": user.daily_request_limit if user else None,
        "daily_token_limit": user.daily_token_limit if user else None,
        "credit_unit": "one generation attempt; definite unsent/rejected calls refunded",
    }


def create_app(settings=None, provider_client=None):
    settings = settings or Settings.from_env()
    settings.validate()

    @asynccontextmanager
    async def lifespan(app):
        db = Database(settings)
        seed(db)
        app.state.db = db
        client = provider_client or httpx.AsyncClient(follow_redirects=False)
        app.state.provider = NvidiaProvider(settings, client)
        try:
            yield
        finally:
            if provider_client is None:
                await client.aclose()
            db.close()

    app = FastAPI(
        title="MGAI AI Platform",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # FastAPI's default validation payload can echo passwords and prompt inputs.
        return JSONResponse(
            {
                "detail": "İstek alanlarını kontrol edin.",
                "fields": [".".join(str(x) for x in e["loc"]) for e in exc.errors()],
                "request_id": getattr(request.state, "request_id", None),
            },
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            "unhandled_error request_id=%s type=%s", request_id, type(exc).__name__
        )
        return JSONResponse(
            {"detail": "Sunucu işlemi tamamlayamadı.", "request_id": request_id},
            status_code=500,
        )

    @app.middleware("http")
    async def security(request, call_next):
        started = time.monotonic()
        request.state.request_id = uid()
        try:
            host = request.url.hostname
            if host not in {
                urlsplit(settings.public_base_url).hostname,
                "127.0.0.1",
                "localhost",
            }:
                raise HTTPException(400, "Sunucu adı doğrulanamadı.")
            is_api = request.url.path.startswith("/api/")
            if is_api:
                client_ip = request.client.host if request.client else "unknown"
                limit(app.state.db, client_ip, "api", 120)
                if request.method in ("POST", "PATCH", "DELETE", "PUT"):
                    check_origin(request, settings)
                    if request.url.path not in (
                        "/api/auth/login",
                        "/api/auth/register",
                    ):
                        principal(request, app.state.db, settings, mutate=True)
            length = request.headers.get("content-length")
            if length is not None:
                try:
                    parsed = int(length)
                except ValueError:
                    raise HTTPException(400, "Geçersiz istek boyutu.") from None
                if parsed < 0 or parsed > 65536:
                    raise HTTPException(413, "İstek en fazla 64 KiB olabilir.")
            received = 0
            original = request._receive

            async def bounded_receive():
                nonlocal received
                message = await original()
                received += len(message.get("body", b""))
                if received > 65536:
                    raise HTTPException(413, "İstek en fazla 64 KiB olabilir.")
                return message

            request._receive = bounded_receive
            response = await call_next(request)
            if received > 65536:
                response = JSONResponse(
                    {"detail": "İstek en fazla 64 KiB olabilir."}, status_code=413
                )
        except HTTPException as exc:
            response = JSONResponse(
                {"detail": exc.detail, "request_id": request.state.request_id},
                status_code=exc.status_code,
                headers=exc.headers,
            )
        except Exception as exc:
            response = await internal_error(request, exc)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Request-ID": request.state.request_id,
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            }
        )
        if not settings.local_dev:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        logger.info(
            json.dumps(
                {
                    "event": "http",
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                },
                ensure_ascii=False,
            )
        )
        return response

    def actor(request, mutate=False, admin=False):
        return principal(request, app.state.db, settings, mutate, admin)[0]

    def logged_in_response(user_id, old_token=None):
        db = app.state.db
        if old_token:
            with db.sessions.begin() as session:
                session.execute(
                    delete(Session).where(Session.token_hash == digest(old_token))
                )
        token = new_session(db, user_id)
        response = JSONResponse({"ok": True})
        response.set_cookie(
            settings.cookie_name,
            token,
            max_age=43200,
            secure=not settings.local_dev,
            httponly=True,
            samesite="lax",
            path="/",
        )
        return response

    @app.get("/health")
    def health():
        return {"ok": True, "service": "mgai"}

    @app.get("/ready")
    def ready():
        try:
            with app.state.db.sessions() as session:
                session.execute(text("SELECT 1"))
                control = session.get(Control, 1)
                worker_ready = bool(
                    control
                    and control.worker_seen_at
                    and control.worker_seen_at > now() - timedelta(seconds=150)
                )
        except SQLAlchemyError:
            return JSONResponse(
                {"ready": False, "database": False, "worker": False}, status_code=503
            )
        return JSONResponse(
            {
                "ready": worker_ready,
                "database": True,
                "worker": worker_ready,
                "nvidia_configured": bool(settings.nvidia_api_key),
            },
            status_code=200 if worker_ready else 503,
        )

    @app.post("/api/auth/login")
    def login(data: Login, request: Request):
        db = app.state.db
        client_ip = request.client.host if request.client else "unknown"
        limit(db, client_ip, "login", 8)
        address = email(data.email)
        limit(db, address, "login_account", 8)
        with db.sessions.begin() as session:
            user = session.scalar(select(User).where(User.email == address))
            valid = verify_password(data.password, user.password_hash if user else None)
            if not user or not valid or not user.active:
                raise HTTPException(401, "E-posta veya parola doğrulanamadı.")
            if PASSWORDS.check_needs_rehash(user.password_hash):
                user.password_hash = hash_password(data.password)
            audit(session, user.id, "auth.login", user.id)
            user_id = user.id
        return logged_in_response(user_id, request.cookies.get(settings.cookie_name))

    @app.post("/api/auth/register")
    def register(data: Register, request: Request):
        db = app.state.db
        limit(db, request.client.host if request.client else "unknown", "register", 5)
        address = email(data.email)
        name = data.name.strip()
        if len(name) < 2:
            raise HTTPException(422, "Ad en az iki karakter olmalı.")
        try:
            with db.sessions.begin() as session:
                invite = session.scalar(
                    select(Invitation)
                    .where(Invitation.token_hash == digest(data.invitation))
                    .with_for_update()
                )
                if (
                    not invite
                    or invite.used
                    or invite.expires_at < now()
                    or invite.email != address
                ):
                    raise HTTPException(
                        403, "Geçerli ve bu e-postaya ait davet gerekli."
                    )
                user = User(
                    email=address,
                    name=name,
                    password_hash=hash_password(data.password),
                    credits=0 if settings.commercial_mode else 20,
                )
                session.add(user)
                session.flush()
                invite.used = True
                session.add(Workspace(owner_id=user.id, name="İlk çalışma alanım"))
                audit(session, user.id, "auth.register", user.id)
                user_id = user.id
        except IntegrityError:
            raise HTTPException(
                409, "Kayıt tamamlanamadı; yöneticinizle görüşün."
            ) from None
        return logged_in_response(user_id)

    @app.get("/api/auth/me")
    def me(request: Request):
        user, csrf = principal(request, app.state.db, settings)
        return {
            "user": user_view(user),
            "csrf_token": csrf,
            "nvidia_configured": bool(settings.nvidia_api_key),
            "commercial_mode": settings.commercial_mode,
            "billing_enabled": False,
        }

    @app.post("/api/auth/logout")
    def logout(request: Request):
        user = actor(request, mutate=True)
        with app.state.db.sessions.begin() as session:
            session.execute(
                delete(Session).where(
                    Session.token_hash == digest(request.cookies[settings.cookie_name])
                )
            )
            audit(session, user.id, "auth.logout", user.id)
        response = JSONResponse({"ok": True})
        response.delete_cookie(
            settings.cookie_name,
            secure=not settings.local_dev,
            httponly=True,
            samesite="lax",
            path="/",
        )
        return response

    @app.post("/api/auth/password")
    def change_password(data: PasswordChange, request: Request):
        user = actor(request, mutate=True)
        with app.state.db.sessions.begin() as session:
            current = session.scalar(
                select(User).where(User.id == user.id).with_for_update()
            )
            if not verify_password(data.current_password, current.password_hash):
                raise HTTPException(401, "Mevcut parola doğrulanamadı.")
            current.password_hash = hash_password(data.new_password)
            session.execute(delete(Session).where(Session.user_id == user.id))
            audit(session, user.id, "auth.password_changed", user.id)
        return logged_in_response(user.id)

    @app.get("/api/workspaces")
    def workspaces(request: Request):
        user = actor(request)
        with app.state.db.sessions() as session:
            rows = session.scalars(
                select(Workspace)
                .where(Workspace.owner_id == user.id)
                .order_by(Workspace.created_at)
            ).all()
            return [
                {
                    "id": w.id,
                    "name": w.name,
                    "description": w.description,
                    "created_at": w.created_at,
                }
                for w in rows
            ]

    @app.post("/api/workspaces", status_code=201)
    def create_workspace(data: WorkspaceCreate, request: Request):
        user = actor(request, mutate=True)
        with app.state.db.sessions.begin() as session:
            session.scalar(select(User).where(User.id == user.id).with_for_update())
            count = session.scalar(
                select(func.count())
                .select_from(Workspace)
                .where(Workspace.owner_id == user.id)
            )
            if count >= 20:
                raise HTTPException(
                    429, "En fazla 20 çalışma alanı oluşturabilirsiniz."
                )
            workspace = Workspace(owner_id=user.id, **data.model_dump())
            session.add(workspace)
            session.flush()
            audit(session, user.id, "workspace.created", workspace.id)
            return {
                "id": workspace.id,
                "name": workspace.name,
                "description": workspace.description,
            }

    @app.get("/api/models")
    def models(request: Request):
        actor(request)
        with app.state.db.sessions() as session:
            return [model_view(m) for m in list_models(session)]

    @app.post("/api/jobs", status_code=202)
    def generate(data: Generate, request: Request):
        user = actor(request, mutate=True)
        limit(app.state.db, user.id, "generation", 5)
        job, created = submit(
            app.state.db,
            settings,
            user.id,
            request.headers.get("idempotency-key", ""),
            data,
        )
        return {**public_job(job), "reused": not created}

    @app.get("/api/jobs")
    def jobs(request: Request, workspace_id: str | None = None):
        user = actor(request)
        with app.state.db.sessions() as session:
            query = select(Job).where(Job.user_id == user.id)
            if workspace_id:
                if not session.scalar(
                    select(Workspace.id).where(
                        Workspace.id == workspace_id, Workspace.owner_id == user.id
                    )
                ):
                    raise HTTPException(404, "Çalışma alanı bulunamadı.")
                query = query.where(Job.workspace_id == workspace_id)
            return [
                public_job(j)
                for j in session.scalars(
                    query.order_by(Job.created_at.desc()).limit(50)
                ).all()
            ]

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str, request: Request):
        user = actor(request)
        with app.state.db.sessions() as session:
            job = session.scalar(
                select(Job).where(Job.id == job_id, Job.user_id == user.id)
            )
            if not job:
                raise HTTPException(404, "İş bulunamadı.")
            return public_job(job, app.state.db, include_content=True)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, request: Request):
        user = actor(request, mutate=True)
        return public_job(cancel(app.state.db, user.id, job_id))

    @app.delete("/api/jobs/{job_id}/content")
    def erase_job(job_id: str, request: Request):
        user = actor(request, mutate=True)
        with app.state.db.sessions.begin() as session:
            job = session.scalar(
                select(Job)
                .where(Job.id == job_id, Job.user_id == user.id)
                .with_for_update()
            )
            if not job:
                raise HTTPException(404, "İş bulunamadı.")
            if job.state in ("queued", "running"):
                raise HTTPException(
                    409, "Önce işin tamamlanmasını veya iptalini bekleyin."
                )
            job.prompt_cipher = None
            job.result_cipher = None
            audit(session, user.id, "job.content_erased", job.id)
        return {"ok": True}

    @app.get("/api/usage")
    def usage(request: Request):
        user = actor(request)
        with app.state.db.sessions() as session:
            return usage_view(session, user)

    @app.get("/api/billing")
    def billing(request: Request):
        actor(request)
        return {
            "enabled": False,
            "state": "not_configured",
            "reason": "Ödeme sağlayıcısı, abonelik planları ve ticari hizmet hakkı henüz onaylanmadı.",
            "credit_unit": "1 metin üretim işi",
            "currency": "USD",
            "plans": [],
        }

    @app.post("/api/billing/checkout")
    def checkout(request: Request):
        actor(request, mutate=True)
        raise HTTPException(503, "Ödeme altyapısı etkin değil; ücret tahsil edilmedi.")

    @app.get("/api/admin/overview")
    def admin_overview(request: Request):
        actor(request, admin=True)
        with app.state.db.sessions() as session:
            return {
                "users": session.scalar(select(func.count()).select_from(User)),
                "workspaces": session.scalar(
                    select(func.count()).select_from(Workspace)
                ),
                "queue": session.scalar(
                    select(func.count())
                    .select_from(Job)
                    .where(Job.state.in_(("queued", "running")))
                ),
                "usage": usage_view(session),
                "nvidia_configured": bool(settings.nvidia_api_key),
                "commercial_mode": settings.commercial_mode,
                "billing_enabled": False,
            }

    @app.get("/api/admin/users")
    def admin_users(request: Request):
        actor(request, admin=True)
        with app.state.db.sessions() as session:
            return [
                user_view(u)
                for u in session.scalars(
                    select(User).order_by(User.created_at.desc()).limit(100)
                ).all()
            ]

    @app.post("/api/admin/invitations", status_code=201)
    def invite(data: Invite, request: Request):
        user = actor(request, mutate=True, admin=True)
        token = secrets.token_urlsafe(32)
        with app.state.db.sessions.begin() as session:
            address = email(data.email)
            session.execute(delete(Invitation).where(Invitation.expires_at < now()))
            session.add(
                Invitation(
                    token_hash=digest(token),
                    email=address,
                    expires_at=now() + timedelta(days=1),
                )
            )
            audit(session, user.id, "invitation.created", digest(address))
        return {
            "invitation": token,
            "email": address,
            "expires_in_seconds": 86400,
            "note": "Davet kodu yalnızca bir kez gösterilir; güvenli bir kanaldan paylaşın.",
        }

    @app.patch("/api/admin/users/{user_id}")
    def update_user(user_id: str, data: UserUpdate, request: Request):
        user = actor(request, mutate=True, admin=True)
        with app.state.db.sessions.begin() as session:
            admins = session.scalars(
                select(User)
                .where(User.role == "admin", User.active.is_(True))
                .order_by(User.id)
                .with_for_update()
            ).all()
            target = session.scalar(
                select(User).where(User.id == user_id).with_for_update()
            )
            if not target:
                raise HTTPException(404, "Kullanıcı bulunamadı.")
            if (
                target.role == "admin"
                and target.active
                and len(admins) == 1
                and (data.role == "member" or data.active is False)
            ):
                raise HTTPException(409, "Son etkin yönetici kaldırılamaz.")
            for field, value in data.model_dump(exclude_none=True).items():
                setattr(target, field, value)
            if not target.active:
                session.execute(delete(Session).where(Session.user_id == user_id))
            audit(session, user.id, "user.updated", user_id)
            return user_view(target)

    @app.post("/api/admin/users/{user_id}/credits")
    def grant_credit(user_id: str, data: CreditGrant, request: Request):
        user = actor(request, mutate=True, admin=True)
        with app.state.db.sessions.begin() as session:
            target = session.scalar(
                select(User).where(User.id == user_id).with_for_update()
            )
            if not target:
                raise HTTPException(404, "Kullanıcı bulunamadı.")
            if target.credits + data.amount > 100000:
                raise HTTPException(422, "Kredi bakiyesi sınırı aşıldı.")
            target.credits += data.amount
            audit(
                session,
                user.id,
                "credits.granted",
                user_id,
                f"amount={data.amount}; reason_sha256={digest(data.reason)}",
            )
            return user_view(target)

    @app.get("/api/admin/models")
    def admin_models(request: Request):
        actor(request, admin=True)
        with app.state.db.sessions() as session:
            return [model_view(m) for m in session.scalars(select(Model)).all()]

    @app.patch("/api/admin/models/{model_id:path}")
    def update_model(model_id: str, data: ModelUpdate, request: Request):
        user = actor(request, mutate=True, admin=True)
        if (
            data.price_input is not None or data.price_output is not None
        ) and not data.pricing_reference:
            raise HTTPException(422, "Fiyat kaynağı veya sözleşme referansı gerekli.")
        if data.commercial_approved and not settings.commercial_mode:
            raise HTTPException(
                403, "Sunucu için ticari hizmet sözleşmesi doğrulanmadı."
            )
        with app.state.db.sessions.begin() as session:
            model = session.scalar(
                select(Model).where(Model.id == model_id).with_for_update()
            )
            if not model:
                raise HTTPException(404, "Model bulunamadı.")
            for field, value in data.model_dump(exclude_none=True).items():
                setattr(model, field, value)
            audit(session, user.id, "model.updated", model_id)
            return model_view(model)

    @app.post("/api/admin/models/refresh")
    async def refresh_models(request: Request):
        user = actor(request, mutate=True, admin=True)
        try:
            available = await app.state.provider.models()
        except ProviderError as exc:
            raise HTTPException(
                429 if exc.code == "rate_limit" else 503,
                exc.message,
                headers={"Retry-After": str(exc.retry_after)}
                if exc.retry_after
                else None,
            ) from None
        with app.state.db.sessions.begin() as session:
            models = session.scalars(select(Model)).all()
            for model in models:
                model.catalog_present = model.id in available
                model.checked_at = now()
            audit(session, user.id, "models.refreshed", "nvidia")
            return [model_view(m) for m in models]

    @app.get("/api/admin/audit")
    def admin_audit(request: Request):
        actor(request, admin=True)
        with app.state.db.sessions() as session:
            rows = session.scalars(
                select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100)
            ).all()
            return [
                {
                    "id": e.id,
                    "actor_id": e.actor_id,
                    "action": e.action,
                    "object_id": e.object_id,
                    "detail": e.detail,
                    "created_at": e.created_at,
                }
                for e in rows
            ]

    @app.api_route(
        "/api/{path:path}", methods=["GET", "POST", "PATCH", "DELETE", "PUT"]
    )
    def unknown_api(path: str):
        raise HTTPException(404, "API yolu bulunamadı.")

    static = Path(settings.static_dir)
    app.mount(
        "/assets",
        StaticFiles(directory=static / "assets", check_dir=False),
        name="assets",
    )

    @app.get("/")
    def index():
        if not (static / "index.html").is_file():
            return JSONResponse(
                {"service": "mgai", "frontend": "Build frontend before preview"},
                status_code=503,
            )
        return FileResponse(static / "index.html")

    return app
