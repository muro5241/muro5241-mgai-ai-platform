# Deployment

This repository is separate from ParaRadar and NOORÉ. Do not replace an existing
static site, change its custom domain/verification files or reuse its deployment
service for MGAI. No live deployment has been performed.

## Local Compose

Run `python scripts/init_env.py` once, then `docker compose up --build -d`.
`.env` is created with cryptographically random local PostgreSQL passwords and a
persistent Fernet key, mode 0600, with no NVIDIA key/admin password. Existing files
are preserved. Docker Compose reads this file for interpolation; it does not pass
owner credentials to runtime containers.

Services: PostgreSQL 17 with a private persistent volume, one-off migration/runtime
role provisioning, worker and API/frontend. Only API loopback port 8080 is exposed.
API/worker containers run as UID 10001, with read-only filesystem, tmpfs, dropped
capabilities and no-new-privileges. Run migrations before service startup; neither
API nor worker has DDL privileges.

Create your first administrator:

```sh
docker compose exec api python -m mgai.bootstrap --email YOUR_EMAIL --name 'MGAI Admin'
```

This prompts without echoing the password. For automation, pipe a protected secret
file into `docker compose exec -T api python -m mgai.bootstrap --email YOUR_EMAIL
--password-file /dev/stdin`. Never put the password in an argument or log it.
Bootstrap refuses to replace an existing administrator. Invitations, roles, credits,
quotas and prices can then be managed from the authenticated admin panel.

Inject NVIDIA_API_KEY through host-managed secrets; a protected local `.env` can be
used for isolated development. Recreate API and worker after changing runtime
secrets. No trial key is synthesized. Leave commercial mode disabled.

## HTTPS production

Provision an actual domain and TLS reverse proxy/load balancer. Set
`PUBLIC_BASE_URL=https://YOUR_ACTUAL_DOMAIN` with no path/trailing slash, and
`LOCAL_DEV=false`. The same origin serves frontend and API; CORS is not opened.
Configure the actual trusted proxy IPs, private networking and limits. Do not use
FORWARDED_ALLOW_IPS=* on an internet-exposed API.

Runtime secrets: DATABASE_URL (least-privilege `postgresql+psycopg://` connection),
DATA_ENCRYPTION_KEY (persistent unique Fernet key), NVIDIA_API_KEY. Non-secret
configuration: PUBLIC_BASE_URL, LOCAL_DEV, GLOBAL_DAILY_REQUESTS, GLOBAL_DAILY_USD_LIMIT.
Commercial agreement reference is required only if commercial mode is deliberately
opened after verification; it cannot establish rights by itself.

Migration task secrets: migration/owner DATABASE_URL and optional APP_DB_PASSWORD
for runtime-role provisioning. On managed PostgreSQL, provision the runtime role
using provider-approved procedures if CREATE ROLE is unavailable. Runtime services
must not receive migration/owner credentials. Enable PostgreSQL TLS via appropriate
connection parameters (for example sslmode=verify-full and a trusted CA).

Use separate API and background worker services from this Docker image. API uses
the image default command; worker command is `python -m mgai.worker`. Both need the
same private database and encryption key. Run `python -m mgai.migrate` as a separate
release task. `/health` is process liveness; `/ready` checks PostgreSQL plus a worker
heartbeat not older than 150 seconds. A configured key is reported separately and
readiness does not claim successful upstream inference.

A new Render web service/worker/database or another Docker host can be used, but
addresses must come from the actually provisioned service. No guessed Render URL,
GPU or callback URI is required for hosted NVIDIA inference.

## Operational checks

Verify login, invite, tenant boundaries, queue dispatch/status, credit reservation,
provider errors, actual pricing and one opt-in real NVIDIA generation before claiming
live integration. Confirm TLS/cookie/CSRF behavior on the actual deployed origin.
Test backup + encryption-key restore and monitor worker staleness/uncertain jobs.
Do not automatically retry uncertain jobs; inspect vendor/account evidence first.
Do not use `docker compose down -v` against persistent user data; ordinary `down`
preserves the database volume. Credits do not represent actual provider billing.
