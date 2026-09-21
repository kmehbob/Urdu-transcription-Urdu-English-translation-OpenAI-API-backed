# Urdu Transcription & Urdu-English Translation (OpenAI API-backed)

Private Urdu speech transcription and Urdu-to-English translation. Record or type Urdu, transcribe it with [OpenAI's `whisper-1`](https://platform.openai.com/docs/guides/speech-to-text) audio API, edit the text, then translate it to fluent English with the [OpenAI Chat Completions API](https://platform.openai.com/docs/guides/text-generation) (default model `gpt-4o-mini`). Both AI services are thin wrappers around the OpenAI API — no local/self-hosted model, and no GPU required anywhere in the stack.

All application code lives in [`server/`](server/).

## Quick start (local, no Docker, no GPU)

```bash
cd server
npm install
cp .env.example .env    # set INTERNAL_SERVICE_TOKEN and a real OPENAI_API_KEY

# gateway
npm start                # http://localhost:3000
```

`.env` only auto-loads into the Node gateway above — the two Python services read env vars directly from their own process environment (no python-dotenv), so load `.env` into each shell before starting `uvicorn`:

```bash
# transcription service (separate shell)
cd ai-services/transcription
pip install -r requirements.txt
set -a; source ../../.env; set +a   # PowerShell: see server/docs/AI_FEATURE.md §5
SERVICE_PORT=8001 uvicorn app:app --host 0.0.0.0 --port 8001

# translation service (separate shell)
cd ai-services/translation
pip install -r requirements.txt
set -a; source ../../.env; set +a
SERVICE_PORT=8002 uvicorn app:app --host 0.0.0.0 --port 8002
```

See [`server/docs/AI_FEATURE.md`](server/docs/AI_FEATURE.md) §5 for the equivalent PowerShell commands.

## Production (Docker Compose)

```bash
cd server
cp .env.example .env    # set INTERNAL_SERVICE_TOKEN and a real OPENAI_API_KEY
./scripts/generate-internal-certs.sh
docker compose build
docker compose up -d
curl http://localhost:3000/api/v1/ready
```

No GPU or NVIDIA Container Toolkit needed — both AI services run on plain `python:3.12-slim` images and call `api.openai.com` over the network.

## Documentation

- [`server/docs/AI_FEATURE.md`](server/docs/AI_FEATURE.md) — architecture, OpenAI model configuration, env var reference, privacy/data lifecycle, rollback, monitoring, QA checklist.
- [`server/docs/DEVOPS_REQUIREMENTS.md`](server/docs/DEVOPS_REQUIREMENTS.md) — deployment/configuration checklist for provisioning a real environment.
- [`server/docs/urdu-voice-pipeline.html`](server/docs/urdu-voice-pipeline.html) — the same material as a standalone, diagram-illustrated visual reference (open directly in a browser).

## Testing

```bash
cd server
npm test                                                       # Node unit tests

cd ai-services/transcription
pip install -r requirements-dev.txt && pytest                  # Python unit tests (no OpenAI credentials needed)

cd ../translation
pip install -r requirements-dev.txt && pytest
```

Gated integration tests that call the real OpenAI API require `RUN_OPENAI_INTEGRATION_TESTS=1` and a funded `OPENAI_API_KEY` — see `npm run test:integration` and the docs above.
