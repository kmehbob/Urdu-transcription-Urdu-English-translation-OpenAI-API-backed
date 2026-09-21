# DevOps Requirements

Configuration/deployment checklist for this project: an Express gateway
serving the browser UI, plus two AI services (Urdu transcription and
Urdu→English translation) that both call the **OpenAI API** — transcription
via OpenAI's `whisper-1` audio transcription endpoint, translation via
OpenAI Chat Completions (default `gpt-4o-mini`). Neither service runs a
local model; there is no GPU requirement anywhere in this stack (see
`docs/AI_FEATURE.md`, architecture note at the top, and §2, for the full
rationale — this replaced an earlier self-hosted-GPU design).

```
Browser  --HTTPS-->  [reverse-proxy: Caddy, optional]  --HTTP-->  gateway (Node/Express, :3000)
                                                                     |  mTLS, internal Docker network only
                                                                     |--> transcription service (Python/FastAPI, :8001) --HTTPS--> api.openai.com
                                                                     |--> translation service   (Python/FastAPI, :8002) --HTTPS--> api.openai.com
```

Only the gateway (or the optional reverse proxy in front of it) is ever
publicly reachable. The AI services are never exposed to the internet, but
they do each make outbound calls to `api.openai.com` on every
transcribe/translate request.

## 1. Host prerequisites

- **OS**: any Linux/Docker host works; there is no GPU-specific base image
  requirement anymore. The Node gateway alone is cross-platform too.
- **Docker Engine** + **Docker Compose v2** (`docker compose`, not the
  standalone `docker-compose` v1 binary).
- **No GPU, no NVIDIA driver, and no NVIDIA Container Toolkit are needed.**
  Both AI service Dockerfiles are plain `python:3.12-slim` images with no
  CUDA/torch/transformers/bitsandbytes/faster-whisper/ctranslate2
  dependencies — this is a deliberate simplification from an earlier
  self-hosted-model design (see `docs/AI_FEATURE.md`'s architecture note).
- **OpenSSL** available on whatever machine runs
  `scripts/generate-internal-certs.sh` (for the internal mTLS certs).
- **Outbound HTTPS egress to `api.openai.com` on every request**, not just
  once at startup — both AI services call the OpenAI API for every single
  transcribe/translate call. This is a harder network requirement than the
  old self-hosted design's "internet once, to download model weights"; the
  `internal` Docker network is intentionally not set to `internal: true` in
  `docker-compose.yml` because of this (see the comment there).
- A valid **`OPENAI_API_KEY`** (see §3) — both AI services fail their
  `/ready` check without one.
- If running the gateway natively instead of in Docker: **Node.js 20**
  (matches the `node:20-alpine` base image) and `npm`.
- If running either Python service natively: **Python 3.12+** (matches the
  `python:3.12-slim` base image).

## 2. Cost, latency, and rate limits (replaces GPU sizing)

There is no hardware to size anymore — this section used to cover GPU/VRAM
tier selection for a self-hosted Whisper/Qwen2.5 stack; that guidance no
longer applies. What DevOps should plan for instead:

- **Per-request cost**: every transcribe/translate call is a billable OpenAI
  API request. Estimate volume × OpenAI's per-token/per-minute pricing for
  the chosen `OPENAI_TRANSCRIBE_MODEL`/`OPENAI_MODEL` before scaling traffic.
- **Rate limits**: OpenAI enforces account-tier rate limits (requests/minute
  and tokens/minute). Set `MAX_CONCURRENT_TRANSCRIPTIONS`/
  `MAX_CONCURRENT_TRANSLATIONS` (per-service) and
  `MAX_CONCURRENT_TRANSCRIBE_REQUESTS`/`MAX_CONCURRENT_TRANSLATE_REQUESTS`
  (gateway-side, §4) so this application's own concurrency can't exceed the
  account's current OpenAI tier — sustained `429`s from OpenAI show up as
  `ai_service_error` in gateway logs (§12).
- **Latency**: now dominated by OpenAI API round-trip time plus network
  egress, not local inference. Full rationale and benchmarking targets:
  `docs/AI_FEATURE.md` §6. Neither service has been benchmarked against the
  real OpenAI API in this environment — treat `docs/AI_FEATURE.md` §6's
  performance targets as what to validate once a real `OPENAI_API_KEY` is in
  use, and retune the concurrency caps above accordingly.

No particular cloud VM shape is required for compute reasons anymore — any
small general-purpose instance is sufficient; size it for the gateway's own
SQLite/audio-storage workload and request concurrency, not for AI inference.

## 3. Secrets to generate/provision before first deploy

1. **`OPENAI_API_KEY`** — required by both AI services (transcription and
   translation); there is no local-model fallback. Provision a real key from
   the OpenAI platform, put it in `.env` (shared via `env_file:` into both
   AI containers), and treat it as a real production secret — it is billable
   and grants API access on the account it belongs to. Without it, both
   services' `/ready` checks report a permanent 503.
2. **`INTERNAL_SERVICE_TOKEN`** — shared bearer secret between the gateway
   and both AI services. Generate with `openssl rand -hex 32` and put the
   same value in `.env` (the single `.env` file is loaded by all three
   containers via `env_file:` in `docker-compose.yml`).
3. **Internal mTLS certificates** — run `./scripts/generate-internal-certs.sh`
   once before `docker compose up` (writes a CA + one server cert per AI
   service + one gateway client cert into `./certs`, mounted read-only into
   all three containers). Re-run any time to rotate all certs. Not committed
   to git — treat `./certs` as secret material.
4. **`CLIENT_API_KEY`** — only needed if you set `REQUIRE_CLIENT_API_KEY=true`
   to lock down the public transcribe/translate endpoints for an
   internal/enterprise deployment (off by default; this ships as an
   unauthenticated public tool otherwise).
5. **TLS certificate for the public domain** — handled automatically by the
   bundled Caddy reverse-proxy profile via Let's Encrypt (see §6) if you use
   it; bring your own otherwise (load balancer, existing proxy, etc.).

Never commit a real `.env` or the `./certs` directory — copy
`.env.example` to `.env` and fill in real values locally/in your secrets
manager.

## 4. Environment variables

Every variable is documented inline in `.env.example` (categorized:
gateway, transcription service, translation service, reverse proxy,
tests) — copy it to `.env` and fill in real values. Key ones DevOps should
explicitly decide on, beyond the generated secrets in §3:

| Variable | Default | Notes |
|---|---|---|
| `ENABLE_AI_FEATURES` | `true` | Instant kill-switch — set `false` + restart gateway to 503 the AI routes without touching anything else (fastest rollback lever). |
| `ALLOWED_ORIGINS` | empty (same-origin only) | Comma-separated list for cross-origin API consumers. |
| `INTERNAL_TLS_ENABLED` | `false` | `docker-compose.yml` forces this to `true`; native/bare-metal runs default it off. |
| `RECORDINGS_RETENTION_DAYS` | `0` (keep forever) | Set a real number for a data-retention policy — auto-deletes audio + transcript + translation older than this. |
| `MAX_AUDIO_UPLOAD_MB` / `MAX_TRANSLATE_TEXT_LENGTH` | `100` / `20000` | Input caps enforced at the gateway. |
| `MAX_CONCURRENT_TRANSCRIBE_REQUESTS` / `MAX_CONCURRENT_TRANSLATE_REQUESTS` | `4` / `8` | Gateway-side concurrency guard, defense-in-depth on top of the per-service semaphores (`MAX_CONCURRENT_TRANSCRIPTIONS`/`MAX_CONCURRENT_TRANSLATIONS`, both `2`) — retune all four against OpenAI's account-level rate limits (§2), not GPU throughput. |
| `RATE_LIMIT_*` | window `60000`ms, transcribe `10`, translate `20`, general `60` | Per-client-IP rate limits. |
| `OPENAI_API_KEY` | *(required)* | Required by both AI services; see §3. No default — missing it fails `/ready` on both services. |
| `OPENAI_TRANSCRIBE_MODEL` | `whisper-1` | Transcription service only. `whisper-1` specifically because it's the only OpenAI transcription model supporting `response_format="verbose_json"` (needed for detected-language + duration fields). |
| `OPENAI_MODEL` | `gpt-4o-mini` | Translation service only. Any OpenAI chat-completions-capable model. |
| `WARMUP_ON_STARTUP` | `false` | Translation service only. Off by default because, unlike warming a local model, it now sends a real billable OpenAI request on every startup. |
| `PUBLIC_DOMAIN` | `localhost` | Real DNS-resolving domain needed for Caddy to obtain a trusted Let's Encrypt cert (§6). |
| `LOG_LEVEL` | `info` | Structured JSON logs; never logs raw transcript/translation text or audio (privacy-by-design, see `docs/AI_FEATURE.md`). |

Note on Docker Compose specifically: `SERVICE_PORT` is overridden per-service
directly in `docker-compose.yml` (not just `.env`), since both AI containers
share the same `.env` file but need different ports (`8001`/`8002`). There
is no per-service model-cache path to override anymore (`MODEL_CACHE_DIR` no
longer exists) — neither AI service caches any model locally.

## 5. Networking / firewall

- **Only publish 443** (and 80, for Let's Encrypt's HTTP-01 challenge if
  using the bundled Caddy profile) on any public-facing firewall.
- **Never expose** 3000 (gateway), 8001 (transcription), or 8002
  (translation) to the public internet. In the default Compose file the
  gateway's port mapping is already loopback-bound
  (`127.0.0.1:3000:3000`) for local testing only; the two AI services
  publish no host port at all and are reachable only from other containers
  on the `internal` Docker network.
- Every gateway↔AI-service call is mutual TLS plus a shared bearer token —
  defense in depth even though the network is already private.
- If terminating TLS with your own load balancer instead of the bundled
  Caddy profile, point it at the gateway container's `:3000` and skip
  opening 80/443 on this host entirely.

## 6. Public HTTPS (optional bundled reverse proxy)

`docker compose --profile proxy up -d` starts a Caddy container
(`deploy/Caddyfile`) that automatically obtains and renews a Let's Encrypt
certificate for `PUBLIC_DOMAIN`, as long as:

1. `PUBLIC_DOMAIN` is set in `.env` to a real domain.
2. DNS A/AAAA record for that domain already points at this host's public
   IP.
3. Ports 80 and 443 are reachable from the internet on this host.

Leaving `PUBLIC_DOMAIN=localhost` (the default) makes Caddy serve its own
locally-trusted cert instead — fine for internal/testing use, not for a
real public deployment.

## 7. Persistent storage

Named Docker volumes (already declared in `docker-compose.yml` — put these
on a **persistent disk**, not ephemeral/local-SSD storage, in any cloud
deployment):

There is no model-cache volume anymore — neither AI service downloads or
caches any model locally; both call the OpenAI API directly on every
request.

| Volume | Contents | Loss impact |
|---|---|---|
| `gateway-data` | SQLite recording-history DB (`data/app.db`) | **Real data loss** — all recording history/metadata |
| `gateway-recordings` | Permanent MP3 audio files | **Real data loss** — all stored audio |
| `gateway-uploads` | Transient multipart-upload staging | Safe to lose (in-flight uploads only) |
| `caddy-data` / `caddy-config` | Caddy's own state, incl. obtained TLS certs | Re-obtains cert from Let's Encrypt on loss (rate-limited — avoid unnecessary resets) |

Back up `gateway-data` and `gateway-recordings` per your organization's data
policy — nothing else in this stack holds data that isn't safely
re-derivable.

## 8. Build & deploy

```bash
cp .env.example .env                        # fill in real secrets (§3)
./scripts/generate-internal-certs.sh        # one-time, before first `up`
docker compose up -d --build                # gateway + transcription + translation
docker compose --profile proxy up -d        # add the public HTTPS proxy, if wanted
```

Startup is fast — there are no model weights to download or load; both AI
containers just need `OPENAI_API_KEY` to create an OpenAI client at
startup.

Resource limits already set per container in `docker-compose.yml`: gateway 1
CPU / 512MB, transcription 512MB, translation 512MB — no GPU reservation for
either AI service anymore. These are much lower than the old self-hosted
defaults (previously 8GB/24GB with a GPU reservation each) since there is no
model resident in RAM/VRAM.

## 9. Health checks / readiness

- Gateway: `GET /health` (liveness; used by its own Docker `HEALTHCHECK`
  and any external uptime monitor). `GET /api/v1/ready` additionally pings
  both AI services with a short timeout.
- Each AI service: its own `/health` exposed via `healthcheck.sh`,
  Docker-native `HEALTHCHECK` in each service's Dockerfile — now a short
  `start_period` (10s) for both services, since there is no local model load
  time to wait out on cold start; `/ready` reports healthy once the OpenAI
  client has been created (which requires `OPENAI_API_KEY` to be set).
- `WARMUP_ON_STARTUP=false` (default, translation service only) — unlike the
  old self-hosted design, "warming up" now means sending a real, billable
  OpenAI API request on every container startup, so it's off by default.
  Set it to `true` only if paying for that startup request to avoid
  first-request latency is an intentional tradeoff.

## 10. Rollback

1. **Fastest, zero-deploy**: set `ENABLE_AI_FEATURES=false`, restart the
   gateway only. All AI routes 503 immediately; static UI and `/health`
   keep working.
2. **Full rollback**: `docker compose stop transcription translation`, or
   redeploy the gateway from an earlier image — it has no required runtime
   dependency on the AI services beyond routing to them.
3. **Disable mTLS** (debugging only, not recommended beyond that): set
   `INTERNAL_TLS_ENABLED=false` / `TLS_ENABLED=false` and switch service
   URLs back to `http://`. Re-enable as soon as possible — this reopens an
   encryption-in-transit gap.

## 11. Testing DevOps should know about

- `npm test` — Node/Jest suite (mocked AI-service calls, real SQLite via a
  temp DB per test file). No GPU, no OpenAI API key needed. Runs in CI.
- `npm run test:integration` — gated integration tests that exercise the
  real services (and, through them, the real OpenAI API), skipped unless
  `RUN_OPENAI_INTEGRATION_TESTS=1` and the real services are up (with a
  valid `OPENAI_API_KEY`; `SAMPLE_URDU_AUDIO_PATH` must point at a real
  `.wav` for the transcription integration test). Renamed from
  `RUN_GPU_INTEGRATION_TESTS` as part of the OpenAI API migration.
- Python side: `ai-services/{transcription,translation}/tests/` (pytest),
  same gate via `RUN_OPENAI_INTEGRATION_TESTS`; unit tests stub the model
  backend so they don't need the `openai` package installed to run.

## 12. Monitoring

- Structured JSON logs to stdout (`LOG_LEVEL`), one line per request with a
  request ID; `transcription_completed.duration_ms` /
  `translation_completed.duration_ms` logged per-request for latency
  tracking against the performance targets in `docs/AI_FEATURE.md` §6.
- Never logs raw transcript/translation text or audio content — only
  operational metadata (sizes, durations, status codes).
- No GPU/VRAM metric to monitor anymore — both AI service containers are
  plain CPU containers. Recommended instead: whatever log/metrics pipeline
  your org standardizes on for ingesting the gateway's stdout JSON lines,
  plus OpenAI-specific monitoring that didn't exist under the old
  self-hosted design — track spend/usage via the OpenAI dashboard or usage
  API for the project's key, and alert on sustained `429`s (surfacing as
  `ai_service_error` in gateway logs), which mean traffic is exceeding the
  account's current OpenAI rate-limit tier (see §2).

## 13. Security checklist before going live

- [ ] Real `OPENAI_API_KEY` provisioned and set in `.env` (both AI services
      fail `/ready` without it).
- [ ] Real `INTERNAL_SERVICE_TOKEN` generated (not the `change-me...`
      placeholder).
- [ ] `./scripts/generate-internal-certs.sh` run, `./certs` kept out of git
      and off any public volume/backup.
- [ ] `INTERNAL_TLS_ENABLED=true` (Compose already forces this).
- [ ] Only 443 (+80 for ACME) open on the public firewall; 3000/8001/8002
      never exposed.
- [ ] `PUBLIC_DOMAIN` set to a real domain with DNS already pointing here,
      if using the bundled Caddy profile.
- [ ] `REQUIRE_CLIENT_API_KEY=true` + a real `CLIENT_API_KEY`, if this is an
      internal/enterprise deployment rather than a public anonymous tool.
- [ ] `RECORDINGS_RETENTION_DAYS` set per your org's data-retention policy
      (default is "keep forever").
- [ ] `gateway-data`/`gateway-recordings` volumes on backed-up, persistent
      (non-ephemeral) storage.
- [ ] Rate limits (`RATE_LIMIT_*`) and concurrency caps
      (`MAX_CONCURRENT_*`) reviewed against expected real traffic and the
      OpenAI account's rate-limit tier (§2), not left at their conservative
      development defaults.

## Reference

Full architecture rationale, model-selection reasoning, prompt-injection
defenses, and compliance notes all live in `docs/AI_FEATURE.md`.
