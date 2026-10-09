import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(16), default="member")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    credits: Mapped[int] = mapped_column(Integer, default=20)
    daily_request_limit: Mapped[int] = mapped_column(Integer, default=20)
    daily_token_limit: Mapped[int] = mapped_column(BigInteger, default=50000)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Invitation(Base):
    __tablename__ = "invitations"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(254))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Model(Base):
    __tablename__ = "models"
    id: Mapped[str] = mapped_column(String(150), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(30), default="nvidia")
    license_name: Mapped[str] = mapped_column(String(100))
    license_url: Mapped[str] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    catalog_present: Mapped[bool] = mapped_column(Boolean, default=False)
    access_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    commercial_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    price_input: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    price_output: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    pricing_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "request_key"),
        Index("ix_jobs_queue", "state", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id"))
    kind: Mapped[str] = mapped_column(String(16), default="text")
    request_key: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), default="queued")
    prompt_cipher: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    result_cipher: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    budget_tokens: Mapped[int] = mapped_column(BigInteger)
    reserved_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    price_input: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    price_output: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    credit_charged: Mapped[bool] = mapped_column(Boolean, default=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    worker_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    hits: Mapped[int] = mapped_column(Integer)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80))
    object_id: Mapped[str] = mapped_column(String(150))
    detail: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BillingEvent(Base):
    """Reserved for a future verified provider adapter, not fake payment success."""

    __tablename__ = "billing_events"
    provider_event_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    state: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Control(Base):
    """Single lock serializes global budget reservations across API replicas."""

    __tablename__ = "control"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
