# Security and data handling

- Provider credentials and data-encryption key exist only on the server. `.env`
  files are Git-ignored and Docker-excluded. No browser key-entry form, arbitrary
  endpoint, user model ID outside the registry or client-provided budget/pricing exists.
- Argon2id passwords use 64 MiB, three passes and at most two concurrent hash/verify
  operations per API process. No default administrator credentials are shipped.
  Login gives the same failure for unknown/incorrect/disabled users; invite tokens
  and session tokens are SHA-256 hashed in PostgreSQL and generated with 256-bit entropy.
- Production cookies are `__Host-`, Secure, HttpOnly, SameSite=Lax with no Domain.
  Exact origin and session CSRF checks protect mutations. Local HTTP is allowed
  only on loopback with explicit LOCAL_DEV. Keep production behind TLS.
- Server-side roles and owner predicates apply to all data paths. The admin panel
  exposes metadata, quotas and audit records, not other users' decrypted job content.
  Browser logout clears cached private workspace/job/admin state and returns to
  overview before another account logs in.
- PostgreSQL runtime role is nonsuperuser, cannot create schema objects and receives
  only CRUD/sequence permissions. Owner/migration credentials are not passed into
  API/worker containers. The default Compose database has no published host port.
- Prompts/results are Fernet-encrypted before PostgreSQL writes. Database metadata
  (email, workspace names/descriptions, model IDs, usage, timestamps, audit actions)
  is not application-encrypted. Protect disks, backups, TLS and access permissions.
- Prompts go to NVIDIA. Do not submit secrets, confidential data or personal data
  until the actual provider agreement/privacy terms permit the use. The UI notes
  provider sharing; review generated claims before use.
- API logs include only request ID, method, route path, status and duration; no
  request bodies, query strings, cookies, passwords, keys or provider raw errors.
  Validation failures omit input values. Credit-reason audit detail stores a hash.
  Configure production log retention/access separately.
- Global API rate limit 120/minute/source IP; login 8/minute/IP and email; signup
  5/minute/IP and generation 5/minute/user. Counters are atomic/persistent. Configure
  only trusted reverse-proxy addresses in FORWARDED_ALLOW_IPS, never wildcard trust
  on an exposed API. Without proxy trust, users behind one proxy share its IP quota.
- 64 KiB body limit applies even to chunked requests. Context/output, request count,
  token reservations and credit counts are bounded. No automatic provider retries,
  redirects, untrusted network tools or automatic social-media publishing exist.
- CSP uses local scripts/styles/assets, frame embedding is denied, responses are
  no-store, and HTTPS production responses include HSTS. The SPA renders provider
  output as text, never raw HTML.

## Retention and recovery

Session/invitation expiry is enforced on read; stale sessions are pruned on login
and stale invitations on new invites. Expired rate buckets are pruned during rate
updates. Job contents can be erased via the owned DELETE API after termination;
queue/idempotency/credit records remain for accounting. Until an automatic retention
policy is configured, content otherwise persists. Establish a retention/deletion
policy and customer export/account deletion before commercial use.

Keep DATA_ENCRYPTION_KEY across restarts and restore it with the database; losing it
makes encrypted prompts/results unreadable. Rotating it without decrypt/re-encrypt
migration is unsupported. A missing/incorrect key never causes the worker to invent
an output: an unreadable job is marked uncertain and requires operator inspection.
Backups and external NVIDIA storage have their own retention policies. Restore
procedures, MFA and account recovery are release work identified in COMMERCIAL-READINESS.md.
