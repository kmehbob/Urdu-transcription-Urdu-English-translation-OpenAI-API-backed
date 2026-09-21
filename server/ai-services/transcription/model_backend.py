"""Thin wrapper around the OpenAI audio transcription API so app.py never
imports it directly.

Keeping the client behind this small surface lets unit tests substitute a
fake backend via `sys.modules['model_backend'] = fake` without installing
the openai package, and mirrors the structure of the translation service's
model_backend.py.
"""
import time

import config
from logging_utils import get_logger, log

logger = get_logger("transcription.model_backend")

_client = None


def load_model():
    """Creates the OpenAI client once. Safe to call multiple times."""
    global _client
    if _client is not None:
        return _client

    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    from openai import OpenAI

    started = time.monotonic()
    log(logger, "info", "creating_openai_client", model=config.OPENAI_TRANSCRIBE_MODEL)
    _client = OpenAI(api_key=config.OPENAI_API_KEY)
    log(logger, "info", "openai_client_ready", load_ms=round((time.monotonic() - started) * 1000))
    return _client


def is_ready():
    return _client is not None


def transcribe_file(file_path, language_override=None):
    """Runs transcription on a local file path via the OpenAI API.

    By default (and for Urdu, the primary use case) the language is forced
    rather than auto-detected, so occasional English words in otherwise-Urdu
    speech are transcribed inline rather than triggering language
    auto-switching mid-utterance. `language_override` lets a caller request
    a different fixed language, or explicit "auto" to let the API detect it
    (useful for genuinely multilingual/unknown-source-language input).
    """
    if _client is None:
        raise RuntimeError("Client not loaded")

    if language_override == "auto":
        language = None
    else:
        language = language_override or config.WHISPER_LANGUAGE

    with open(file_path, "rb") as audio_file:
        request_kwargs = dict(
            model=config.OPENAI_TRANSCRIBE_MODEL,
            file=audio_file,
            response_format="verbose_json",
        )
        if language:
            request_kwargs["language"] = language
        result = _client.audio.transcriptions.create(**request_kwargs)

    return {
        "text": (result.text or "").strip(),
        "language": getattr(result, "language", None) or language or config.WHISPER_LANGUAGE,
        "duration_seconds": getattr(result, "duration", None),
    }
