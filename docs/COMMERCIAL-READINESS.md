# Commercial release boundary

The MVP is a foundation for a SaaS, not a launched paid service. The owner must
complete the items that depend on external accounts and jurisdiction before
customer access. No generated configuration can grant contractual rights.

1. Verify NVIDIA service production/third-party access rights under the actual
   accepted account terms and obtain the appropriate agreement/paid offering.
   Review each model's license, attribution and acceptable-use conditions.
   Keep the evidence/reference and verified pricing. See NVIDIA-ACCESS.md.
2. Provision an HTTPS domain and managed PostgreSQL/backup storage, configure
   protected runtime/migration credentials, preserve the encryption key, create
   the first administrator securely and inject the real NVIDIA key.
3. Choose and activate an appropriate payment-provider account (such as Stripe
   where supported). Do not add a secret until an actual adapter is implemented.
   Payments are currently disabled deliberately; commercial mode does not enable them.
4. An adapter must bind provider customers/subscriptions to users on the server,
   use reviewed plan/price IDs, verify webhook signatures over original bytes
   and timestamps, reject replayed provider_event_id values transactionally,
   reconcile disputed/reversed payments and grant credits only from verified
   provider state. Never accept amounts, credits or success redirects from clients.
5. Add subscription lifecycle, cancellation/refund/proration, invoices, taxes,
   legal entity, terms/privacy notices, data-processing terms and applicable user
   rights. Invite-only internal accounts are not a replacement for these obligations.
6. Implement email verification, secure account recovery, MFA for administrators,
   tenant/organization membership rules, deletion/export workflows, support/abuse
   escalation and deployment monitoring appropriate to the target market.
7. Recheck dependency/image advisories, license drift, load/concurrency limits,
   backups/restores/key rotation, operational incident response and penetration
   testing. Tests in this repo cover the MVP; they do not certify production security.

Future media services need approved model/service licenses, bounded private object
storage, validated upload/download URLs, asynchronous provider status, signed
short-lived delivery URLs, separate modality quotas and real end-to-end tests.
No model is advertised as producing images/audio/video in this MVP.
