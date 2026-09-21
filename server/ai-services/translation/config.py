import os


def _bool(value, default):
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


SERVICE_PORT = _int(os.environ.get("SERVICE_PORT"), 8002)
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")

# Mutual TLS for the gateway<->service link. When enabled, uvicorn (started
# via the Dockerfile CMD) terminates TLS and requires a client certificate
# signed by TLS_CLIENT_CA_FILE - see scripts/generate-internal-certs.sh.
TLS_ENABLED = _bool(os.environ.get("TLS_ENABLED"), False)
TLS_CERT_FILE = os.environ.get("TLS_CERT_FILE", "")
TLS_KEY_FILE = os.environ.get("TLS_KEY_FILE", "")
TLS_CLIENT_CA_FILE = os.environ.get("TLS_CLIENT_CA_FILE", "")

# Translation is delegated to the OpenAI API - no local model/GPU. Left
# empty by default so a missing key fails clearly at load_model() (caught by
# app.py's lifespan handler, surfaced as a permanent 503 via /ready) instead
# of at import time, matching how INTERNAL_SERVICE_TOKEN is handled above.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

MAX_CONTEXT_TOKENS = _int(os.environ.get("MAX_CONTEXT_TOKENS"), 4096)
MAX_NEW_TOKENS = _int(os.environ.get("MAX_NEW_TOKENS"), 1024)
MAX_INPUT_TOKENS_PER_CHUNK = _int(os.environ.get("MAX_INPUT_TOKENS_PER_CHUNK"), 700)
MAX_CONCURRENT_TRANSLATIONS = _int(os.environ.get("MAX_CONCURRENT_TRANSLATIONS"), 2)

# Deterministic / low-temperature generation, appropriate for translation.
TEMPERATURE = _float(os.environ.get("TEMPERATURE"), 0.1)
TOP_P = _float(os.environ.get("TOP_P"), 0.9)
DO_SAMPLE = _bool(os.environ.get("DO_SAMPLE"), False)

# Defense in depth: the gateway already enforces this, the service enforces
# it again so it is never reachable directly without the same protection.
MAX_TRANSLATE_TEXT_LENGTH = _int(os.environ.get("MAX_TRANSLATE_TEXT_LENGTH"), 20000)

# Off by default: unlike warming up a local model, this sends a real (paid)
# request to the OpenAI API on every startup.
WARMUP_ON_STARTUP = _bool(os.environ.get("WARMUP_ON_STARTUP"), False)

# Fail fast at startup on a bad config value instead of a confusing failure
# deep inside a request handler.
if MAX_CONCURRENT_TRANSLATIONS <= 0:
    raise ValueError(f"MAX_CONCURRENT_TRANSLATIONS must be a positive integer, got {MAX_CONCURRENT_TRANSLATIONS}")
if MAX_CONTEXT_TOKENS <= 0:
    raise ValueError(f"MAX_CONTEXT_TOKENS must be a positive integer, got {MAX_CONTEXT_TOKENS}")
if MAX_NEW_TOKENS <= 0:
    raise ValueError(f"MAX_NEW_TOKENS must be a positive integer, got {MAX_NEW_TOKENS}")
if MAX_INPUT_TOKENS_PER_CHUNK <= 0:
    raise ValueError(f"MAX_INPUT_TOKENS_PER_CHUNK must be a positive integer, got {MAX_INPUT_TOKENS_PER_CHUNK}")
