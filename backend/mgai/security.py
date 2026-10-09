import hashlib
import re
import secrets
import threading
import time
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from .models import AuditEvent, RateBucket, Session, User, now

PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(24))
PASSWORD_LOCK = threading.BoundedSemaphore(2)


def hash_password(password):
    with PASSWORD_LOCK:
        return PASSWORDS.hash(password)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def email(value):
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(
        r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+", value
    ):
        raise HTTPException(422, "Geçerli bir e-posta adresi girin.")
    return value


def verify_password(password, hashed):
    try:
        with PASSWORD_LOCK:
            return PASSWORDS.verify(hashed or DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False


def check_origin(request, settings):
    if request.headers.get("origin") != settings.public_base_url:
        raise HTTPException(403, "İstek kaynağı doğrulanamadı.")


def principal(request, db, settings, mutate=False, admin=False):
    token = request.cookies.get(settings.cookie_name, "")
    if not token or len(token) > 200:
        raise HTTPException(401, "Giriş yapın.")
    with db.sessions() as session:
        row = session.execute(
            select(Session, User)
            .join(User)
            .where(
                Session.token_hash == digest(token),
                Session.expires_at > now(),
                User.active.is_(True),
            )
        ).first()
        if not row:
            raise HTTPException(401, "Oturum sona erdi; yeniden giriş yapın.")
        auth, user = row
        if mutate:
            check_origin(request, settings)
            if not secrets.compare_digest(
                auth.csrf, request.headers.get("x-csrf-token", "")
            ):
                raise HTTPException(403, "CSRF doğrulaması başarısız.")
        if admin and user.role != "admin":
            raise HTTPException(403, "Yönetici yetkisi gerekli.")
        return user, auth.csrf


def new_session(db, user_id):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with db.sessions.begin() as session:
        session.execute(delete(Session).where(Session.expires_at < now()))
        session.add(
            Session(
                token_hash=digest(token),
                user_id=user_id,
                csrf=csrf,
                expires_at=now() + timedelta(hours=12),
            )
        )
    return token


def limit(db, identifier, scope, count, period=60):
    current = int(time.time()) // period
    key = digest(scope + ":" + identifier)
    with db.sessions.begin() as session:
        statement = insert(RateBucket).values(key=key, window=current, hits=1)
        hits = session.scalar(
            statement.on_conflict_do_update(
                index_elements=[RateBucket.key, RateBucket.window],
                set_={"hits": RateBucket.hits + 1},
            ).returning(RateBucket.hits)
        )
        # All current limit windows use 60 seconds. Keep no more than two hours.
        session.execute(delete(RateBucket).where(RateBucket.window < current - 120))
    if hits > count:
        raise HTTPException(
            429,
            "Hız sınırı doldu; kısa bir süre sonra tekrar deneyin.",
            headers={"Retry-After": str(period)},
        )


def audit(session, actor, action, object_id, detail=""):
    session.add(
        AuditEvent(actor_id=actor, action=action, object_id=object_id, detail=detail)
    )
