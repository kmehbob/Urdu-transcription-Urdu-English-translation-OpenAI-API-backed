"""Thin wrapper around the OpenAI Chat Completions API, kept separate from
app.py so unit tests can substitute a fake backend without an OpenAI client
installed.
"""
import time

import config
import prompt as prompt_module
from logging_utils import get_logger, log

logger = get_logger("translation.model_backend")

_client = None
_encoding = None


def load_model():
    global _client, _encoding
    if _client is not None:
        return _client

    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    import tiktoken
    from openai import OpenAI

    started = time.monotonic()
    log(logger, "info", "creating_openai_client", model=config.OPENAI_MODEL)

    _client = OpenAI(api_key=config.OPENAI_API_KEY)
    try:
        _encoding = tiktoken.encoding_for_model(config.OPENAI_MODEL)
    except KeyError:
        _encoding = tiktoken.get_encoding("o200k_base")

    log(logger, "info", "openai_client_ready", load_ms=round((time.monotonic() - started) * 1000))

    if config.WARMUP_ON_STARTUP:
        try:
            translate_one("سلام")
            log(logger, "info", "translation_warmup_complete")
        except Exception as exc:  # pragma: no cover - exercised only with real deps installed
            log(logger, "warning", "translation_warmup_failed", error_type=type(exc).__name__)

    return _client


def is_ready():
    return _client is not None


def count_tokens(text):
    if _encoding is None:
        raise RuntimeError("Client not loaded")
    if not text:
        return 0
    return len(_encoding.encode(text))


def translate_one(text, source_language="ur", target_language="en"):
    """Translates a single bounded chunk of text (already within
    MAX_INPUT_TOKENS_PER_CHUNK) and returns only the translated text."""
    if _client is None:
        raise RuntimeError("Client not loaded")

    messages = prompt_module.build_messages(text, source_language, target_language)

    request_kwargs = dict(model=config.OPENAI_MODEL, messages=messages, max_tokens=config.MAX_NEW_TOKENS)
    if config.DO_SAMPLE:
        request_kwargs["temperature"] = config.TEMPERATURE
        request_kwargs["top_p"] = config.TOP_P
    else:
        request_kwargs["temperature"] = 0

    response = _client.chat.completions.create(**request_kwargs)
    return (response.choices[0].message.content or "").strip()
