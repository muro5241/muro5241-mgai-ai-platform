# Validation — 2026-10-09

## Model update and production preparation

- Default model: `nvidia/nemotron-3-super-120b-a12b`. Direct actual NVIDIA generation returned HTTP 200, Turkish text, `finish_reason=stop`, 57 input/123 output tokens in 5.4 seconds. The MGAI provider live test separately passed after the default changed (no MockTransport in that test).
- Current local backend suite: **65 passed, 1 skipped**, **87.21% coverage** (minimum 85%). Real PostgreSQL 17 and four actual HTTPS Chromium tests. The skipped optional live test was run independently and passed.
- Frontend: **4 Vitest tests passed**, TypeScript and production Vite build passed.
- Ruff lint/format and Git whitespace checks passed.
- Production Compose configuration parsed and validated with `config --quiet`; no expanded secret configuration was printed.
- New regression checks verify default model selection, rejection of the 404 model even if re-enabled, historical model/job preservation, migration of a populated initial schema, managed PostgreSQL app-role configuration, generated Fernet compatibility, private production configuration and Render owner-credential isolation.

Ordinary job/browser tests mock only NVIDIA upstream responses and explicitly label those responses as tests. They are not real provider evidence. The opt-in live test is distinct.

## Container and CI verification

The first new local image build failed because the builder lacked the cloud proxy's DNS/network path. A supported host-network/proxy/CA retry preserves artifact hashes and TLS verification. Consult the latest PR CI for final Docker/Compose outcomes; do not count an unfinished workflow as passed.

Previous MVP code passed full fresh-runner Docker Compose PostgreSQL/migrations/worker/API/frontend/admin/login/workspace checks, non-root/read-only runtime, owner-credential isolation and restart persistence. Historical run: https://github.com/muro5241/muro5241-mgai-ai-platform/actions/runs/37865297263

## Not verified or not implemented

- No real public MGAI HTTPS address has been created or verified; no production studio/worker generation or backup restore has been exercised on a public host.
- No hosting credentials/CLI login were available. GitHub Actions secret-list access returned 403. Render's current pricing/schema endpoints were blocked; the Blueprint was checked locally, not provider-validated. Cost estimates and account actions are in `PRODUCTION-RELEASE.md`.
- Real NVIDIA success does not verify hosted commercial/resale rights or current prices. Billing, media inference and TikTok/YouTube connectors remain inactive/unimplemented extension work.
- ParaRadar and NOORÉ were not changed during this update.
