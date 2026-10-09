# Validation — 2026-10-09 UTC

## Executed in the Codex cloud machine

- Backend: **57 passed, 1 skipped**, **87.09% coverage** (required minimum 85%). Real PostgreSQL 17, restricted runtime database role, and four real HTTPS Chromium browser tests were used.
- Frontend: **2 Vitest tests passed**; TypeScript and production Vite build passed.
- Ruff lint and formatting checks passed.
- Multi-stage Docker image built successfully (`mgai-ai-platform:local`).
- Fresh GitHub runner: full Compose PostgreSQL/migrations/worker/API/frontend stack passed. Functional admin bootstrap, login, workspace creation, honest missing-key rejection, non-root/read-only runtime, owner-credential isolation and persistence across API/worker restart all passed.
- Frontend production dependency audit reported zero known vulnerabilities; `pip check` found no broken requirements. These checks are not a security certification.
- Public NVIDIA catalog GET returned HTTP 200 with 80 models. Both initial Nemotron 70B/51B IDs were present. Catalog membership does not verify this account's generation entitlement.

The browser generation tests mock only the external NVIDIA HTTP response. They exercise the actual app, PostgreSQL queue, worker, encrypted results, quota accounting and browser. Their synthetic response explicitly says it is a test result. They are **not real NVIDIA generation tests**.

## Remaining verification

- The real generation test was skipped because `NVIDIA_API_KEY` is absent. It requires a securely supplied key and `RUN_LIVE_NVIDIA=1`; one bounded request consumes account credits.
- Compose startup initially exposed an incorrectly quoted tmpfs option; it was fixed. Local cloud startup remains blocked by the full Docker/root filesystem. CI initially exposed root-owned PostgreSQL bind-directory cleanup; the smoke test now uses an isolated Compose volume, and the fresh-runner stack check passed.
- No public HTTPS deployment, real customer billing, media inference or third-party project connectors were activated.
- NVIDIA trial service terms could not be retrieved (HTTP 403). A model's commercial license does not establish this NVIDIA account's right to resell hosted inference. Commercial mode remains disabled.

Validated code commit: `f465dd6aa6b454547b164e86520c537d74d59989`. [Independent GitHub Actions run](https://github.com/muro5241/muro5241-mgai-ai-platform/actions/runs/37865297263). Later documentation-only changes do not change that tested code. Earlier failed/cancelled diagnostic runs remain visible in Actions history.
