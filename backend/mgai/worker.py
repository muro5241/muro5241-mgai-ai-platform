"""PostgreSQL queue: exclusive claims; never retry an ambiguously dispatched call."""

import asyncio
import logging
from datetime import timedelta
from decimal import Decimal

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from .config import Settings
from .database import Database
from .jobs import lock_budget, model_allowed
from .models import Control, Job, Model, User, now, uid
from .providers import NvidiaProvider, ProviderError
from .registry import seed
from .security import audit

logger = logging.getLogger("mgai.worker")


def recover(db):
    with db.sessions.begin() as session:
        stale = session.scalars(
            select(Job)
            .where(Job.state == "running", Job.lease_expires_at < now())
            .with_for_update(skip_locked=True)
        ).all()
        for job in stale:
            if job.dispatched_at:
                job.state = "uncertain"
                job.error_code = "worker_interrupted"
                job.error_message = "Başlatılan NVIDIA isteğinin sonucu doğrulanamadı; otomatik tekrar yapılmadı."
                job.completed_at = now()
            else:
                job.state = "queued"
            job.lease_expires_at = None


def claim(db, worker_id):
    recover(db)
    with db.sessions.begin() as session:
        job = session.scalar(
            select(Job)
            .where(Job.state == "queued")
            .order_by(Job.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        job.state = "running"
        job.worker_id = worker_id
        job.lease_expires_at = now() + timedelta(seconds=120)
        return job.id


async def process_one(db, settings, provider, worker_id=None):
    worker_id = worker_id or uid()
    with db.sessions.begin() as session:
        session.get(Control, 1).worker_seen_at = now()
    job_id = claim(db, worker_id)
    if not job_id:
        return False
    result = None
    error = None
    try:
        with db.sessions.begin() as session:
            job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            user = session.get(User, job.user_id)
            model = session.get(Model, job.model_id)
            if not user or not user.active:
                raise ProviderError("account_disabled", "Hesap devre dışı.")
            try:
                model_allowed(settings, model)
            except HTTPException:
                raise ProviderError(
                    "model_disabled", "Model kullanımı durduruldu."
                ) from None
            payload = db.decrypt(job.prompt_cipher)
            model_id = job.model_id
            owner_id = job.user_id
            job.dispatched_at = now()
        # Total deadline is shorter than the lease, including providers that drip data.
        async with asyncio.timeout(80):
            result = await provider.generate(model_id, payload)
    except TimeoutError:
        error = ProviderError(
            "timeout",
            "NVIDIA yanıtı doğrulanamadı; otomatik tekrar yapılmadı.",
            uncertain=True,
        )
    except ProviderError as exc:
        error = exc
    except Exception as exc:
        logger.error("worker_error job_id=%s type=%s", job_id, type(exc).__name__)
        error = ProviderError(
            "worker_error",
            "İş sonucu doğrulanamadı; otomatik tekrar yapılmadı.",
            uncertain=True,
        )
    with db.sessions.begin() as session:
        # Same lock order as reservations and cancellation; no cross-process budget race.
        owner_id = session.scalar(select(Job.user_id).where(Job.id == job_id))
        user = lock_budget(session, owner_id)
        job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job.state != "running" or job.worker_id != worker_id:
            return True
        job.completed_at = now()
        job.lease_expires_at = None
        if result is not None:
            job.state = "succeeded"
            verified_model = session.get(Model, job.model_id)
            verified_model.access_verified = True
            verified_model.checked_at = now()
            job.result_cipher = db.encrypt(result)
            usage = result.get("usage")
            if usage:
                job.prompt_tokens = usage["prompt_tokens"]
                job.completion_tokens = usage["completion_tokens"]
                job.budget_tokens = job.prompt_tokens + job.completion_tokens
                if job.price_input is not None and job.price_output is not None:
                    job.cost_usd = (
                        Decimal(job.prompt_tokens) * job.price_input
                        + Decimal(job.completion_tokens) * job.price_output
                    ) / Decimal(1_000_000)
        else:
            job.state = "uncertain" if error.uncertain else "failed"
            job.error_code = error.code
            job.error_message = error.message
            if not error.uncertain:
                user.credits += int(job.credit_charged)
                job.credit_charged = False
                job.budget_tokens = 0
                job.reserved_cost = Decimal(0)
        audit(session, owner_id, "job." + job.state, job.id)
    return True


async def run():
    settings = Settings.from_env()
    settings.validate()
    db = Database(settings)
    seed(db)
    worker_id = uid()
    try:
        async with httpx.AsyncClient(follow_redirects=False) as client:
            provider = NvidiaProvider(settings, client)
            while True:
                try:
                    worked = await process_one(db, settings, provider, worker_id)
                except Exception as exc:
                    logger.error("worker_cycle_error type=%s", type(exc).__name__)
                    worked = False
                if not worked:
                    await asyncio.sleep(1)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(run())
