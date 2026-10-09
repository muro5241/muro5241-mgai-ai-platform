# MGAI production release preparation — 2026-10-09

**No public MGAI deployment has been performed or verified.** The NVIDIA provider
was genuinely exercised with `nvidia/nemotron-3-super-120b-a12b`; that does not prove
an HTTPS app/queue/worker deployment, production resale rights or invoiced cost.
ParaRadar and NOORÉ are outside this deployment and must not be imported or changed.

## Existing account access

The current Codex machine has no Render/Railway/Fly/other hosting API credential or
Render CLI login. GitHub repository access works, but GitHub's integration returned
403 when listing this repository's Actions secrets; that does not establish whether
any hidden deployment secret exists. No paid resources, DNS records or existing
services were changed. No account key was requested in chat or printed.

Render pricing/docs endpoints returned an outbound proxy 403. Their domains were
added to the environment draft; the owner must save/publish it before expecting
those requests to work. This is not a successful provider-side Blueprint validation.
Public official Render CLI/provider sources on GitHub were readable and were used
for credential locations and deployment capability/plan names.

## Option A: separate Render resources

`render.yaml` creates only new `mgai-*` resources in Frankfurt:

- `mgai-api`: paid Docker web service, frontend compiled into the same image and
  served by FastAPI on the same origin. Render supplies HTTPS and its actual
  `RENDER_EXTERNAL_URL`; no guessed onrender.com address is required.
- `mgai-worker`: paid background worker, same private PostgreSQL and encryption
  secret; command `python -m mgai.worker`.
- `mgai-postgres`: PostgreSQL 17, private network only, basic 256 MB/5 GB starting
  storage. Increase memory/storage with load; this is an initial small MVP setup.
- `mgai-migrations`: separate Docker cron task with the owner connection. Trigger
  **Run manually** after database creation and for each approved release. Its
  annual UTC fallback is a provider scheduling requirement, not automatic per-release
  migration. Pause/delete the task between releases if that fallback is unwanted;
  recreate it before a later release. API/worker never receive owner credentials.

The reviewed PR branch is explicit and automatic deployments are disabled. Change
all service branch references to the approved release/main together when promoting.
Validate the Blueprint in the Render dashboard/official CLI before creating paid
resources; local YAML/security checks do not validate the provider's current schema.

Owner/account steps:

1. Create a **new** Blueprint from this MGAI repository, review its new resource list
   and actual prices. Do not import the ParaRadar static site or NOORÉ services.
2. Supply the actual NVIDIA key in each API/worker **secret environment field**.
   Codex proxy-bound secrets must not be copied as literal placeholders to another
   host; set the actual key through Render's secret UI. Values are never in this repo.
3. Run `mgai-migrations` once after the database is available. API/worker can fail or
   remain unready until this completes; redeploy them after migration succeeds.
4. In API service Shell, create the first admin using
   `python -m mgai.bootstrap --email YOUR_EMAIL --name 'MGAI Admin'`. The password
   prompt does not echo. No default admin password is created.
5. Use the actual assigned API URL for verification below. With a custom domain,
   set `PUBLIC_BASE_URL` to that actual HTTPS origin on the API. The background
   worker has no public URL; its default origin is unused by its queue loop.

The shared environment group generates a random app-role password and persistent
`DATA_ENCRYPTION_SECRET`. The runtime derives its Fernet key with SHA-256 and URL-safe
base64; this avoids treating a generic generated string as a Fernet key. Existing
`DATA_ENCRYPTION_KEY` takes precedence and remains supported. **Preserve/back up the
original secret or key; changing it makes existing encrypted content unreadable.**
The app connection always uses `mgai_app`; managed `postgres://` owner connections
are normalized only in the migration task. Runtime internal connections request
TLS (`PGSSLMODE=require`); enable verify-full with the provider's matching hostname
and trusted CA where supported. Review actual proxy IPs before trusting forwarded
client headers; do not set unrestricted proxy trust on an exposed API. Until then
limits are conservative and may count clients together behind Render's proxy.

## Costs — estimates, not a verified quote

Render's current account/checkout prices could **not** be fetched in this environment.
Planning estimates based on commonly published starter rates:

| Item | Estimated USD/month |
|---|---:|
| API + frontend, starter | 7 |
| Worker, starter | 7 |
| PostgreSQL basic 256 MB compute | 6 |
| PostgreSQL 5 GB storage at $0.30/GB | 1.50 |
| Migration cron minimum | 1 |
| **Estimated hosting subtotal** | **22.50** |

These are **unconfirmed estimates**. Confirm the current region/account checkout
before purchase; actual plans, taxes, workspace fees, storage, backups and egress
can differ. No resources were purchased. NVIDIA inference is additional and its
account-specific price is unknown; free trial credits do not establish a production
price or resale permission. Initial model prices stay unknown in MGAI. The request
cap is enforced, but the configured USD cap cannot bound unpriced inference. Set
verified model rates and references before relying on cost limits.

Render uses its HTTPS hostname without a paid custom domain. Optional domain/DNS
and additional backup charges depend on the selected account/provider.

## Option B: a dedicated Docker host with automatic HTTPS

Use a new host/project, at least 2 GB RAM and enough storage for image builds plus
PostgreSQL/backups. Provider-specific cost cannot be verified without an account;
budget roughly $10–20/month for a small 2 GB VM, plus storage/backup/domain/inference.
This is an estimate, not a provider quote. Keep ports 80/443 open; do not publish
PostgreSQL or the API container directly. Point an actual new MGAI hostname to it.

```sh
python scripts/init_production_env.py --hostname YOUR_ACTUAL_HOSTNAME --email YOUR_TLS_EMAIL
# Inject NVIDIA_API_KEY through the host's secure environment/secret mechanism.
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml up -d --build --wait
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml exec api python -m mgai.bootstrap --email YOUR_EMAIL
```

The initializer writes only generated local database/encryption secrets into a new
0600 `.env.production`; it **does not copy the NVIDIA key** and refuses to overwrite
existing encryption keys. `compose.production.yaml` removes the API's loopback
published port, adds Caddy with persistent TLS storage, serves frontend/API together
and trusts only Caddy's fixed private IP. Ensure subnet 172.30.86.0/24 is unused on
the host; change subnet and proxy address together if necessary. Do not run `down -v`
against persistent production data. Preserve PostgreSQL and encryption-key backups.

## Verification and release gate

```sh
python scripts/verify_https.py https://YOUR_ACTUAL_DEPLOYED_ORIGIN
```

This requires valid public TLS, the MGAI frontend and production security headers,
healthy PostgreSQL, a live worker heartbeat and a configured server key. It does
not bypass certificates or claim that key presence proves inference.

Then log in on that actual URL, confirm Nemotron 3 Super is preselected, create one
owned workspace and run one bounded Turkish job. Verify success, real returned text,
provider usage and the quota change. Check another invited account's isolation and
restart persistence. Record actual URL and results before calling the system live.
Neither a localhost test nor a direct NVIDIA API success is this final verification.

Keep `COMMERCIAL_MODE=false`, invitation-only access and payments off until the
account holder confirms hosted production/third-party service rights and model
license conditions. Model licensing and API account permission are separate.
