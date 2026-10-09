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

The initial local builder lacked the cloud proxy DNS mapping. Supplying the supported proxy settings, host mapping and verified CA fixed it without disabling TLS or hash checks. The final local Docker build and full Compose functional/restart checks passed. Caddy 2.10.2 configuration validation passed with dropped capabilities; no public certificate was requested or verified.

Both push and PR CI passed for code commit `dabda5b02877a88366010d8e671ebc30ee8bcd37`, including the complete tests, production Compose parsing, Docker build and functional Compose smoke test. [PR CI run](https://github.com/muro5241/muro5241-mgai-ai-platform/actions/runs/37870462351). Subsequent documentation-only updates do not change the validated code.

Previous MVP code passed full fresh-runner Docker Compose PostgreSQL/migrations/worker/API/frontend/admin/login/workspace checks, non-root/read-only runtime, owner-credential isolation and restart persistence. Historical run: https://github.com/muro5241/muro5241-mgai-ai-platform/actions/runs/37865297263

## Not verified or not implemented

- No real public MGAI HTTPS address has been created or verified; no production studio/worker generation or backup restore has been exercised on a public host.
- No hosting credentials/CLI login were available. GitHub Actions secret-list access returned 403. Render's current pricing/schema endpoints were blocked; the Blueprint was checked locally, not provider-validated. Cost estimates and account actions are in `PRODUCTION-RELEASE.md`.
- Real NVIDIA success does not verify hosted commercial/resale rights or current prices. Billing, media inference and TikTok/YouTube connectors remain inactive/unimplemented extension work.
- ParaRadar and NOORÉ were not changed during this update.
