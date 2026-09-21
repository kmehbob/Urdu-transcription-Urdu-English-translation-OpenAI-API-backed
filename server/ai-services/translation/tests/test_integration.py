"""Integration test against the REAL OpenAI API.
Skipped unless RUN_OPENAI_INTEGRATION_TESTS=1. Requires requirements.txt
(the openai/tiktoken deps, not requirements-dev.txt) to be installed and a
valid OPENAI_API_KEY in the environment.
"""
import os

import pytest

RUN_INTEGRATION = os.environ.get("RUN_OPENAI_INTEGRATION_TESTS") == "1"


@pytest.mark.skipif(not RUN_INTEGRATION, reason="set RUN_OPENAI_INTEGRATION_TESTS=1 to run against the real OpenAI API")
def test_real_api_translates():
    import model_backend

    model_backend.load_model()
    assert model_backend.is_ready()

    translation = model_backend.translate_one("میرا نام علی ہے۔")
    assert "ali" in translation.lower()
