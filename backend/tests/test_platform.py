import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest
from conftest import BASE, MODEL, PASSWORD, enqueue, login, request_body
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from mgai.app import create_app
from mgai.jobs import submit
from mgai.models import Invitation, Job, Model, Session, User, now
from mgai.schemas import Generate
from mgai.security import digest, limit
from mgai.worker import claim, process_one, recover


def run_worker(app):
    return asyncio.run(
        process_one(app.state.db, app.state.settings, app.state.provider)
    )


def test_auth_cookie_csrf_logout(client, auth, db):
    token = client.cookies.get("__Host-mgai_session")
    with db.sessions() as s:
        assert s.get(Session, digest(token)) and not s.get(Session, token)
    for patch in ({"Origin": "https://attacker.test"}, {"X-CSRF-Token": "bad"}):
        assert (
            client.post(
                "/api/workspaces", headers={**auth, **patch}, json={"name": "Bad"}
            ).status_code
            == 403
        )
    assert client.post("/api/auth/logout", headers=auth).status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_login_errors_and_no_password_echo(client):
    for address in ("admin@example.test", "unknown@example.test"):
        r = client.post(
            "/api/auth/login",
            headers={"Origin": BASE},
            json={"email": address, "password": "wrong-password-2026"},
        )
        assert (
            r.status_code == 401
            and r.json()["detail"] == "E-posta veya parola doğrulanamadı."
        )
    r = client.post(
        "/api/auth/login",
        headers={"Origin": BASE},
        json={"email": "admin@example.test", "password": "secret"},
    )
    assert r.status_code == 422 and "secret" not in r.text and "input" not in r.text
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.test", "password": PASSWORD},
        ).status_code
        == 403
    )


def test_invitation_registration_role_single_use(client, auth, db):
    r = client.post(
        "/api/admin/invitations", headers=auth, json={"email": "new@example.test"}
    )
    assert r.status_code == 201
    token = r.json()["invitation"]
    with db.sessions() as s:
        assert s.get(Invitation, digest(token)) and not s.get(Invitation, token)
    data = {
        "email": "new@example.test",
        "name": "New User",
        "password": PASSWORD,
        "invitation": token,
    }
    assert (
        client.post(
            "/api/auth/register",
            headers={"Origin": BASE},
            json={**data, "email": "other@example.test"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/auth/register", headers={"Origin": BASE}, json=data
        ).status_code
        == 200
    )
    assert client.get("/api/auth/me").json()["user"]["role"] == "member"
    assert client.get("/api/admin/users").status_code == 403
    assert (
        client.post(
            "/api/auth/register", headers={"Origin": BASE}, json=data
        ).status_code
        == 403
    )


def test_password_change_rotates_sessions(client, auth, db):
    old = client.cookies.get("__Host-mgai_session")
    r = client.post(
        "/api/auth/password",
        headers=auth,
        json={"current_password": PASSWORD, "new_password": "new-password-only-2026"},
    )
    assert r.status_code == 200
    with db.sessions() as s:
        assert s.get(Session, digest(old)) is None
    assert client.get("/api/auth/me").status_code == 200
    assert (
        client.post(
            "/api/auth/login",
            headers={"Origin": BASE},
            json={"email": "admin@example.test", "password": PASSWORD},
        ).status_code
        == 401
    )


def test_tenant_isolation_even_admin(client, auth, member):
    own = enqueue(client, auth).json()["id"]
    login(client, "member@example.test")
    assert client.get("/api/jobs/" + own).status_code == 404
    assert client.get("/api/jobs").json() == []
    assert client.get("/api/admin/users").status_code == 403
    other = client.get("/api/workspaces").json()[0]["id"]
    auth = login(client)
    assert (
        enqueue(
            client,
            {**auth, "Idempotency-Key": "tenant-check-key-0002"},
            workspace_id=other,
        ).status_code
        == 404
    )
    assert client.get("/api/jobs", params={"workspace_id": other}).status_code == 404


def test_encrypted_queue_idempotency_and_reported_usage(client, auth, app, db, vendor):
    first = enqueue(client, auth)
    assert first.status_code == 202 and first.json()["state"] == "queued"
    job_id = first.json()["id"]
    assert client.get("/api/usage").json()["credits"] == 99
    second = enqueue(client, auth)
    assert second.json()["id"] == job_id and second.json()["reused"]
    assert enqueue(client, auth, max_tokens=128).status_code == 409
    assert run_worker(app) and not run_worker(app)
    result = client.get("/api/jobs/" + job_id).json()
    assert result["state"] == "succeeded"
    assert (
        result["cost_usd"] is None
        and result["budget_tokens"] == 110
        and len(vendor.requests) == 1
    )
    with db.sessions() as s:
        job = s.get(Job, job_id)
        assert "gerçek NVIDIA".encode() not in job.result_cipher
        assert db.decrypt(job.result_cipher)["usage"]["completion_tokens"] == 30
        assert s.get(Model, MODEL).access_verified
    assert client.get("/api/usage").json()["reported_completion_tokens"] == 30


def test_cancel_refunds_only_queued(client, auth, app):
    job_id = enqueue(client, auth).json()["id"]
    assert (
        client.post("/api/jobs/" + job_id + "/cancel", headers=auth).status_code == 200
    )
    assert client.get("/api/usage").json()["credits"] == 100 and not run_worker(app)
    assert (
        client.post("/api/jobs/" + job_id + "/cancel", headers=auth).status_code == 409
    )


@pytest.mark.parametrize(
    "status,state,refund",
    [
        (401, "failed", True),
        (403, "failed", True),
        (429, "failed", True),
        (500, "uncertain", False),
        (302, "failed", True),
        (404, "failed", True),
    ],
)
def test_provider_errors_no_retry_or_key_leak(
    client, auth, app, vendor, status, state, refund
):
    vendor.response = httpx.Response(
        status,
        text="test-provider-api-key confidential body",
        headers={"Location": "https://attacker.test", "Retry-After": "120"},
    )
    job_id = enqueue(client, auth).json()["id"]
    run_worker(app)
    r = client.get("/api/jobs/" + job_id)
    assert r.json()["state"] == state
    assert "confidential" not in r.text and "test-provider-api-key" not in r.text
    assert r.json()["credit_charged"] is not refund
    assert len(vendor.requests) == 1 and not run_worker(app)


@pytest.mark.parametrize(
    "error", [httpx.ReadTimeout("secret"), httpx.ConnectError("secret")]
)
def test_ambiguous_network_failure_keeps_budget(client, auth, app, vendor, error):
    vendor.response = error
    job_id = enqueue(client, auth).json()["id"]
    run_worker(app)
    r = client.get("/api/jobs/" + job_id).json()
    assert r["state"] == "uncertain" and r["credit_charged"]
    assert client.get("/api/usage").json()["credits"] == 99 and not run_worker(app)


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        {"choices": []},
        {"choices": [None]},
        {"choices": [{"finish_reason": "stop", "message": {"content": ""}}]},
        {"choices": [{"finish_reason": "stop", "message": {"content": "a" * 32001}}]},
        {
            "choices": [{"finish_reason": "stop", "message": {"content": "valid"}}],
            "usage": {"prompt_tokens": -1, "completion_tokens": 2},
        },
    ],
)
def test_invalid_provider_output(client, auth, app, vendor, body):
    vendor.response = httpx.Response(200, json=body)
    job_id = enqueue(client, auth).json()["id"]
    run_worker(app)
    assert client.get("/api/jobs/" + job_id).json()["state"] == "uncertain"


def test_partial_output_and_unknown_usage_are_explicit(client, auth, app, vendor):
    vendor.response = httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": "Partial real-format text"},
                }
            ]
        },
    )
    job_id = enqueue(client, auth).json()["id"]
    run_worker(app)
    r = client.get("/api/jobs/" + job_id).json()
    assert (
        r["state"] == "succeeded"
        and r["result"]["truncated"]
        and r["result"]["usage"] is None
    )
    assert (
        r["prompt_tokens"] is None
        and r["budget_tokens"] > 1024
        and r["cost_usd"] is None
    )


def test_lease_recovery_cannot_duplicate_dispatch(client, auth, db):
    job_id = enqueue(client, auth).json()["id"]
    assert claim(db, "first") == job_id
    with db.sessions.begin() as s:
        s.get(Job, job_id).lease_expires_at = now() - timedelta(seconds=1)
    recover(db)
    with db.sessions() as s:
        assert s.get(Job, job_id).state == "queued"
    claim(db, "second")
    with db.sessions.begin() as s:
        j = s.get(Job, job_id)
        j.dispatched_at = now()
        j.lease_expires_at = now() - timedelta(seconds=1)
    recover(db)
    with db.sessions() as s:
        assert s.get(Job, job_id).state == "uncertain"
    assert claim(db, "third") is None


def test_parallel_worker_claims_exclusive(client, auth, db):
    for i in range(3):
        assert (
            enqueue(
                client, {**auth, "Idempotency-Key": f"test-request-key-{i:04d}"}
            ).status_code
            == 202
        )
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = list(pool.map(lambda i: claim(db, f"worker-{i}"), range(3)))
    assert len(set(jobs)) == 3 and None not in jobs


def test_concurrent_credit_reservations_atomic(client, auth, db, admin, settings):
    body = Generate(**request_body(client))
    with db.sessions.begin() as s:
        s.get(User, admin).credits = 1

    def attempt(i):
        try:
            return submit(db, settings, admin, f"concurrent-key-{i:04d}", body)[1]
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=5) as pool:
        r = list(pool.map(attempt, range(5)))
    assert r.count(True) == 1 and r.count(402) == 4


def test_request_token_and_global_limits(client, auth, db, admin, settings):
    body = Generate(**request_body(client))
    with db.sessions.begin() as s:
        s.get(User, admin).daily_request_limit = 1
    submit(db, settings, admin, "first-request-key", body)
    with pytest.raises(HTTPException) as e:
        submit(db, settings, admin, "second-request-key", body)
    assert e.value.status_code == 429
    with db.sessions.begin() as s:
        u = s.get(User, admin)
        u.daily_request_limit = 20
        u.daily_token_limit = 2048
    with pytest.raises(HTTPException):
        submit(db, settings, admin, "token-request-key", body)
    with db.sessions.begin() as s:
        s.get(User, admin).daily_token_limit = 50000
    with pytest.raises(HTTPException):
        submit(
            db,
            replace(settings, global_daily_requests=1),
            admin,
            "global-request-key",
            body,
        )


def test_price_snapshot_and_global_spend_cap(client, auth, db, admin, app, settings):
    r = client.patch(
        "/api/admin/models/" + MODEL,
        headers=auth,
        json={
            "price_input": "2",
            "price_output": "4",
            "pricing_reference": "test-only pricing contract reference",
        },
    )
    assert r.status_code == 200
    body = Generate(**request_body(client))
    with pytest.raises(HTTPException):
        submit(
            db,
            replace(settings, global_daily_usd_limit="0.000001"),
            admin,
            "cost-limit-key-0",
            body,
        )
    job_id = enqueue(client, auth).json()["id"]
    with db.sessions.begin() as s:
        s.get(Model, MODEL).price_output = Decimal(999)
    run_worker(app)
    assert Decimal(client.get("/api/jobs/" + job_id).json()["cost_usd"]) == Decimal(
        "0.00028"
    )


def test_commercial_gates_cannot_be_bypassed(client, auth, db, admin, settings):
    body = Generate(**request_body(client))
    commercial = replace(
        settings,
        commercial_mode=True,
        commercial_agreement_reference="test-only-not-real-contract",
    )
    with pytest.raises(HTTPException) as e:
        submit(db, commercial, admin, "commercial-key-000", body)
    assert e.value.status_code == 403
    assert (
        client.patch(
            "/api/admin/models/" + MODEL,
            headers=auth,
            json={"commercial_approved": True},
        ).status_code
        == 403
    )


def test_admin_last_role_and_grants(client, auth, admin):
    for patch in ({"active": False}, {"role": "member"}):
        assert (
            client.patch(
                "/api/admin/users/" + admin, headers=auth, json=patch
            ).status_code
            == 409
        )
    r = client.post(
        "/api/admin/users/" + admin + "/credits",
        headers=auth,
        json={"amount": 20, "reason": "test-only grant"},
    )
    assert r.status_code == 200 and r.json()["credits"] == 120
    assert any(
        e["action"] == "credits.granted" for e in client.get("/api/admin/audit").json()
    )


def test_catalog_presence_not_generation_access(client, auth):
    r = client.post("/api/admin/models/refresh", headers=auth)
    assert r.status_code == 200
    m = next(m for m in r.json() if m["id"] == MODEL)
    assert m["catalog_present"] and not m["access_verified"]


def test_missing_key_disables_only_generation(settings, db, admin, vendor):
    app = create_app(
        replace(settings, nvidia_api_key=""),
        httpx.AsyncClient(transport=httpx.MockTransport(vendor.handler)),
    )
    with TestClient(app, base_url=BASE) as c:
        auth = login(c)
        assert enqueue(c, auth).status_code == 503
        assert (
            c.get("/api/auth/me").json()["nvidia_configured"] is False
            and not vendor.requests
        )


def test_model_disabled_before_dispatch(client, auth, app, vendor):
    job_id = enqueue(client, auth).json()["id"]
    assert (
        client.patch(
            "/api/admin/models/" + MODEL, headers=auth, json={"enabled": False}
        ).status_code
        == 200
    )
    run_worker(app)
    assert (
        client.get("/api/jobs/" + job_id).json()["state"] == "failed"
        and not vendor.requests
    )


def test_erase_content_billing_disabled(client, auth, app, db):
    job_id = enqueue(client, auth).json()["id"]
    assert (
        client.delete("/api/jobs/" + job_id + "/content", headers=auth).status_code
        == 409
    )
    run_worker(app)
    assert (
        client.delete("/api/jobs/" + job_id + "/content", headers=auth).status_code
        == 200
    )
    assert client.get("/api/jobs/" + job_id).json()["result"] is None
    with db.sessions() as s:
        assert s.get(Job, job_id).prompt_cipher is None
    assert not client.get("/api/billing").json()["enabled"]
    assert client.post("/api/billing/checkout", headers=auth).status_code == 503


def test_health_body_host_and_security_headers(client, auth, app):
    assert client.get("/health").json() == {"ok": True, "service": "mgai"}
    assert client.get("/ready").status_code == 503
    run_worker(app)
    assert client.get("/ready").status_code == 200
    r = client.get("/api/models")
    assert (
        "frame-ancestors" in r.headers["content-security-policy"]
        and r.headers["cache-control"] == "no-store"
    )
    assert (
        client.post("/api/jobs", headers=auth, content=b"x" * 65537).status_code == 413
    )
    assert client.get("/health", headers={"Host": "attacker.test"}).status_code == 400
    assert client.get("/api/unknown").status_code == 404


@pytest.mark.parametrize(
    "updates",
    [
        {"max_tokens": 99999},
        {"kind": "video"},
        {"messages": [{"role": "system", "content": "bad"}]},
        {"messages": [{"role": "user", "content": "x" * 8001}]},
        {"messages": [{"role": "assistant", "content": "invalid last role"}]},
        {"nvidia_api_key": "secret-in-payload"},
    ],
)
def test_input_limits(client, auth, updates):
    r = enqueue(client, auth, **updates)
    assert r.status_code == 422 and "secret-in-payload" not in r.text


def test_runtime_database_role_is_not_owner(db):
    with db.sessions() as s:
        assert (
            s.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user"))
            is False
        )
        with pytest.raises(ProgrammingError):
            s.execute(text("CREATE TABLE forbidden_test (id integer)"))


def test_rate_counter_under_concurrency(db):
    def attempt(i):
        try:
            limit(db, "test", "counter", 3)
            return 200
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        r = list(pool.map(attempt, range(6)))
    assert r.count(200) == 3 and r.count(429) == 3


@pytest.mark.parametrize(
    "changes",
    [
        {"public_base_url": "http://example.com"},
        {"database_url": "sqlite:///:memory:"},
        {"encryption_key": "bad"},
        {"nvidia_api_key": "bad key"},
        {"commercial_mode": True},
        {"global_daily_requests": 0},
    ],
)
def test_invalid_settings(settings, changes):
    with pytest.raises(ValueError):
        replace(settings, **changes).validate()


def test_secrets_not_in_repr(settings):
    assert "test-provider-api-key" not in repr(
        settings
    ) and settings.encryption_key not in repr(settings)


def test_worker_health_tracks_real_heartbeat(client, auth, app, settings, monkeypatch):
    from mgai.health import main

    monkeypatch.setenv("DATABASE_URL", settings.database_url)
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", settings.encryption_key)
    monkeypatch.setenv("PUBLIC_BASE_URL", BASE)
    assert main() == 1
    run_worker(app)
    assert main() == 0


def test_disabled_account_blocks_dispatch(client, auth, member, app, vendor):
    user_id, workspace_id = member
    member_auth = login(client, "member@example.test")
    job_id = enqueue(client, member_auth).json()["id"]
    admin_auth = login(client)
    assert (
        client.patch(
            "/api/admin/users/" + user_id, headers=admin_auth, json={"active": False}
        ).status_code
        == 200
    )
    run_worker(app)
    with app.state.db.sessions() as session:
        job = session.get(Job, job_id)
        assert (
            job.state == "failed"
            and job.error_code == "account_disabled"
            and not job.credit_charged
        )
    assert not vendor.requests


def test_worker_total_deadline_is_uncertain(client, auth, app):
    job_id = enqueue(client, auth).json()["id"]

    class TimedOut:
        async def generate(self, model, payload):
            raise TimeoutError()

    asyncio.run(process_one(app.state.db, app.state.settings, TimedOut()))
    assert client.get("/api/jobs/" + job_id).json()["state"] == "uncertain"
