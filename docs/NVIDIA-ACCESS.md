# NVIDIA access and commercial-use review

Checked on **2026-10-09 UTC**. Commercial/customer service remains disabled.
This is a technical evidence record, not confirmation of this account's contractual rights.

## Current verified default — 2026-10-09

A genuine authenticated Turkish generation request to
`nvidia/nemotron-3-super-120b-a12b` returned HTTP 200 and complete text: 57 input
+ 123 output tokens, 5.4 seconds, finish reason `stop`. This was an actual provider
response, not a mock. The application's NVIDIA provider live test also passed after
the model switch. The previous 70B generation returned HTTP 404 despite appearing
in the live model catalog; it is disabled and rejected for new jobs, while historic
job foreign keys are preserved. 51B remains optional and was not genuinely tested.

The [official Super model card](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b)
was retrieved. It links the [NVIDIA Nemotron Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/)
and separately the API Trial Terms. It documents `enable_thinking=False`, used by
the successful request and now applied to this model in MGAI. Its supported-language
list does not list Turkish; one successful output is not a comprehensive quality
assessment. Commercial model readiness is not hosted-account resale permission.

## Historical catalog/license checks

1. The live official endpoint `GET https://integrate.api.nvidia.com/v1/models`
   returned **HTTP 200**, without an API key, with 80 model IDs. This is a real
   catalog read, **not** a real text-generation or account-entitlement test.
2. Both configured model IDs were present:
   `nvidia/llama-3.1-nemotron-70b-instruct` and
   `nvidia/llama-3.1-nemotron-51b-instruct`.
3. Official catalog pages were fetched and inspected:
   - [Nemotron 70B](https://build.nvidia.com/nvidia/llama-3_1-nemotron-70b-instruct)
   - [Nemotron 51B](https://build.nvidia.com/nvidia/llama-3_1-nemotron-51b-instruct)
   Their embedded official API reference specifies the HTTPS OpenAI-compatible
   chat-completion endpoint and Bearer authentication. The 70B card states:
   **“This model is ready for commercial use.”** It separately links the Llama
   3.1 license, acceptable-use policy and privacy policy. The 51B page's API
   reference names the Llama 3.1 license. These statements do not confer hosted
   service resale rights or guarantee access for any particular API key.
4. The [Meta Llama 3.1 Community License](https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/LICENSE)
   was retrieved from Meta's official GitHub. It grants limited, non-transferable,
   royalty-free use subject to conditions, including “Built with Llama” attribution,
   license/notice obligations, acceptable-use terms and a separate license for
   entities above the specified 700 million monthly active user threshold. The
   exact retrieved license text is retained in `licenses/LLAMA-3.1.txt`.
5. Official Build UI text links the
   [NVIDIA API Trial Terms of Service PDF](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf)
   and warns not to upload confidential information or personal data. The PDF
   request returned **403** in this cloud environment. Therefore its exact current
   trial restrictions, production/resale permission, retention and account-specific
   terms could **not** be verified here. NVIDIA agreement pages on `www.nvidia.com`
   were also blocked by the outbound proxy. Network domains were added to the
   onboarding draft for owner review; saving a draft does not publish it.

## Model selection changed after the live check

The Llama 3.3 70B and Mistral Small 3.1 24B catalog web pages were reachable, but
neither model ID appeared in the actual `/v1/models` response. They were therefore
not selected as this MVP's defaults. This does not prove those models are globally
retired; catalog scope/account/provider differences require further verification.

The older Mistral 7B v0.3 endpoint was listed, but its NVIDIA card stated “ready for
non-commercial use” while its API metadata mentioned Apache 2.0. This ambiguity
must be resolved against the actual model and hosted-service terms before commercial
use; that model is excluded from this registry.

Public catalog presence, account generation access, underlying model license,
NVIDIA hosted-service terms, and verified pricing are **different facts**.
The API and UI preserve that distinction. Catalog refresh sets `catalog_present`;
`access_verified` is set only after a successful generation. It is historical
per-server evidence, not a guarantee that permissions/credits are still valid.

## Default gate and account-owner actions

- The MVP is invitation-only and intended for the owner's permitted internal
  evaluation/workflows. It is not enabled for paying customers. Even internal
  usage must comply with the account's accepted trial/evaluation terms.
- `COMMERCIAL_MODE=false`, no active billing adapter, no checkout and no public
  self-registration. An API key by itself never enables commercial mode.
- Commercial mode requires a documented NVIDIA agreement reference in protected
  server configuration, a separate model approval and verified input/output prices.
  The configuration is an operator assertion; it cannot itself establish legal rights.
- Before customer access, the account owner must read/accept the actual account
  terms, obtain explicit production/third-party service rights from NVIDIA (or
  arrange a properly licensed self-hosted/paid deployment), resolve model-specific
  terms, record the evidence and set contractual price references. Do not interpret
  free credits or a trial key as resale authorization.
- Obtain an actual NVIDIA Build key, then enter `NVIDIA_API_KEY` only in Codex's
  secure personal secret setting for the live test, or the deployment host's secret
  environment settings for runtime. The allowed hostname is
  `integrate.api.nvidia.com`. Never paste the key into chat, GitHub, frontend code,
  command-line arguments or screenshots. Normal tests need no real key.
- If the pending network settings are needed, review/save/publish the environment
  configuration. For the new SaaS workflow, remove any stale mandatory TikTok rows
  in the settings UI; they are not required by MGAI. The draft tool is additive and
  cannot delete those earlier requirements.

## Real test

With the key already injected securely:

```sh
cd backend
RUN_LIVE_NVIDIA=1 python -m pytest tests/test_live_nvidia.py -q
```

This makes a real model-list request and exactly one bounded 128-output-token
text-generation request. It may consume account credits. No retries or video
publishing occur. It tests the provider contract, not the full deployed SaaS or
commercial rights. The existing real-provider generation test is currently **skipped**
because the key is absent. Mock responses are explicitly labelled in tests and
preview screenshots; they are not evidence of live NVIDIA generation.
