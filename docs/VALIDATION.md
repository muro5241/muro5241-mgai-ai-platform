# Validation — 2026-10-09 UTC

## Executed in the Codex cloud machine

- Backend: **57 passed, 1 skipped**, **87.09% coverage** (required minimum 85%). Real PostgreSQL 17, restricted runtime database role, and four real HTTPS Chromium browser tests were used.
- Frontend: **2 Vitest tests passed**; TypeScript and production Vite build passed.
- Ruff lint and formatting checks passed.
- Multi-stage Docker image built successfully (`mgai-ai-platform:local`).
- Public NVIDIA catalog GET returned HTTP 200 with 80 models. Both initial Nemotron 70B/51B IDs were present. Catalog membership does not verify this account's generation entitlement.

The browser generation tests mock only the external NVIDIA HTTP response. They exercise the actual app, PostgreSQL queue, worker, encrypted results, quota accounting and browser. Their synthetic response explicitly says it is a test result. They are **not real NVIDIA generation tests**.

## Remaining verification

- The real generation test was skipped because `NVIDIA_API_KEY` is absent. It requires a securely supplied key and `RUN_LIVE_NVIDIA=1`; one bounded request consumes account credits.
- Compose startup initially exposed an incorrectly quoted tmpfs option; that configuration was fixed. The subsequent local startup was blocked by the cloud machine's full Docker/root filesystem (`no space left on device`). The built image alone is not a successful Compose startup test. CI additionally exercises the complete Compose stack on a fresh runner.
- No public HTTPS deployment, real customer billing, media inference or third-party project connectors were activated.
- NVIDIA trial service terms could not be retrieved (HTTP 403). A model's commercial license does not establish this NVIDIA account's right to resell hosted inference. Commercial mode remains disabled.

See GitHub Actions for independent CI outcomes on the PR; an uncompleted workflow must not be counted as passed.
