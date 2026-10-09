# MGAI AI Platform

An isolated FastAPI + React/TypeScript AI workspace MVP with PostgreSQL, a durable
worker queue and NVIDIA Build hosted text models. Its Turkish responsive interface
includes login, project workspaces, model selection, chat/text generation, job
history, credit/usage tracking and administrator controls.

**Current status:** core application, PostgreSQL and browser flows are testable;
real NVIDIA generation needs an account-owned key. Commercial resale rights are
not confirmed, payments are disabled, and this is not a production SaaS launch.
ParaRadar and NOORÉ repositories are untouched. Naming a workspace after an existing
project does not connect to, modify or publish anything in that project.

## Run locally with Docker

```sh
python scripts/init_env.py
docker compose up --build -d
docker compose exec api python -m mgai.bootstrap --email owner@example.com --name 'MGAI Admin'
```

Replace the email with your own. The last command securely prompts for your own
12+ character administrator password; it is never a command-line argument or a
built-in default. The first command generates unique local PostgreSQL/encryption
credentials into an ignored mode-0600 `.env`, preserves existing files and leaves
`NVIDIA_API_KEY` empty. API listens on loopback port 8080; development HTTP is
allowed only for loopback with `LOCAL_DEV=true`. See [deployment](docs/DEPLOYMENT.md)
for HTTPS production configuration and noninteractive secure bootstrap.

Add `NVIDIA_API_KEY` only through protected server secret settings. No fake key or
fake output is used when it is absent: generation returns 503, while login and
workspace management still work. Read [NVIDIA access/terms review](docs/NVIDIA-ACCESS.md)
before using trial credentials or opening customer access.

## Tests

```sh
python -m venv .venv
.venv/bin/python -m pip install --require-hashes -r backend/requirements-dev.lock
.venv/bin/python -m playwright install --with-deps chromium
.venv/bin/python scripts/run_checks.py
```

The runner creates and removes a disposable real PostgreSQL 17 container, runs
Alembic migrations, provisions a least-privilege runtime role, builds/tests the UI,
then runs backend and real HTTPS Chromium tests. No SQLite substitution and no real
NVIDIA key are required. `RUN_LIVE_NVIDIA=1` separately opts into the real provider
contract test when a secure key is available. See [validation](docs/VALIDATION.md).

## MVP boundaries

- Invitation-only registration, Argon2id passwords, hashed opaque sessions,
  HttpOnly/Secure cookies in production, Origin/CSRF checks, server-side roles,
  password rotation/revocation, rate limits and bounded inputs.
- Owner-scoped workspaces and jobs. Global administrators manage account metadata
  and quotas but cannot read another user's private prompts/results through job APIs.
- Two currently listed NVIDIA text models, fixed HTTPS provider destination,
  server-only keys, model catalog refresh and distinct catalog/actual-access states.
- PostgreSQL `FOR UPDATE SKIP LOCKED` jobs, atomic quota/credit reservations,
  persisted idempotency keys, lease recovery, encrypted prompts/results, cancellation
  before dispatch and honest uncertain-status handling without automatic provider retries.
- A credit is one generation job, **not** a dollar or a provider token. Definite
  unsent/rejected jobs are refunded; ambiguous calls retain reservation. Every job
  counts against the rolling request quota, including cancellation and failure.
- Reported tokens, conservative pending/unknown token reservations and per-job price
  snapshots. Prices start unknown; provider credits and invoice totals are not fabricated.
  A configurable server request cap always applies; a USD cost cap requires verified
  prices and cannot protect unpriced requests by itself.
- Readiness includes PostgreSQL and fresh worker heartbeat. Runtime DB credentials
  cannot create tables; migrations use a separate owner connection.
- Image/audio/video adapter protocols are extension points only, not working media
  services. TikTok/YouTube automation connectors and direct repo synchronization are
  not implemented or authorized by workspace creation.
- Payment adapter interface and idempotent-event storage are prepared; no payment
  provider, subscription billing, checkout or payment webhooks are enabled.

See [architecture](docs/ARCHITECTURE.md), [security](docs/SECURITY.md), and
[commercial readiness](docs/COMMERCIAL-READINESS.md). Built with Llama;
[Llama 3.1 license](docs/licenses/LLAMA-3.1.txt).
