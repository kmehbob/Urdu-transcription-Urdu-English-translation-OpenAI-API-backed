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


SERVICE_PORT = _int(os.environ.get("SERVICE_PORT"), 8001)
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")

# Mutual TLS for the gateway<->service link. When enabled, uvicorn (started
# via the Dockerfile CMD) terminates TLS and requires a client certificate
# signed by TLS_CLIENT_CA_FILE - see scripts/generate-internal-certs.sh.
TLS_ENABLED = _bool(os.environ.get("TLS_ENABLED"), False)
TLS_CERT_FILE = os.environ.get("TLS_CERT_FILE", "")
TLS_KEY_FILE = os.environ.get("TLS_KEY_FILE", "")
TLS_CLIENT_CA_FILE = os.environ.get("TLS_CLIENT_CA_FILE", "")

# Transcription is delegated to the OpenAI audio API - no local model/GPU.
# Left empty by default so a missing key fails clearly at load_model()
# (caught by app.py's lifespan handler, surfaced as a permanent 503 via
# /ready) instead of at import time.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
# whisper-1 is the only OpenAI transcription model that supports
# response_format="verbose_json", which is what gives us the per-request
# detected `language` and `duration` this service's response shape needs.
OPENAI_TRANSCRIBE_MODEL = os.environ.get("OPENAI_TRANSCRIBE_MODEL", "whisper-1")

# Forced/default source language (ISO-639-1) passed to the API. See
# transcribe_file() in model_backend.py for how a per-request override or
# "auto" interacts with this default.
WHISPER_LANGUAGE = os.environ.get("WHISPER_LANGUAGE", "ur")

MAX_AUDIO_UPLOAD_MB = _int(os.environ.get("MAX_AUDIO_UPLOAD_MB"), 100)
MAX_CONCURRENT_TRANSCRIPTIONS = _int(os.environ.get("MAX_CONCURRENT_TRANSCRIPTIONS"), 2)

ALLOWED_CONTENT_TYPES = {
    "audio/webm",
    "audio/mp3",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/ogg",
    "audio/aac",
    "audio/x-m4a",
    "application/octet-stream",  # some mobile browsers omit/garble the type
}

EXTENSION_BY_CONTENT_TYPE = {
    "audio/mp3": "mp3",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/webm": "webm",
    "audio/wav": "wav",
    "audio/ogg": "ogg",
    "audio/aac": "aac",
}

# Fail fast at startup on a bad config value instead of a confusing failure
# deep inside a request handler.
if MAX_CONCURRENT_TRANSCRIPTIONS <= 0:
    raise ValueError(f"MAX_CONCURRENT_TRANSCRIPTIONS must be a positive integer, got {MAX_CONCURRENT_TRANSCRIPTIONS}")
if MAX_AUDIO_UPLOAD_MB <= 0:
    raise ValueError(f"MAX_AUDIO_UPLOAD_MB must be a positive integer, got {MAX_AUDIO_UPLOAD_MB}")
