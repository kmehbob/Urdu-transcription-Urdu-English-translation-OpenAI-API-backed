import model_backend
import config


class FakeTranscription:
    def __init__(self, text, language, duration):
        self.text = text
        self.language = language
        self.duration = duration


class FakeTranscriptions:
    def __init__(self, response):
        self.response = response
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self.response


class FakeAudio:
    def __init__(self, response):
        self.transcriptions = FakeTranscriptions(response)


class FakeClient:
    def __init__(self, response):
        self.audio = FakeAudio(response)


def _install_fake_client(monkeypatch, response):
    fake = FakeClient(response)
    monkeypatch.setattr(model_backend, "_client", fake)
    return fake


def test_no_override_uses_configured_default_language(monkeypatch, tmp_path):
    fake = _install_fake_client(monkeypatch, FakeTranscription("hello", "ur", 1.5))
    monkeypatch.setattr(config, "WHISPER_LANGUAGE", "ur")
    audio_path = tmp_path / "fake.mp3"
    audio_path.write_bytes(b"fake-audio-bytes")

    model_backend.transcribe_file(str(audio_path))
    assert fake.audio.transcriptions.last_kwargs["language"] == "ur"


def test_auto_override_omits_language_kwarg(monkeypatch, tmp_path):
    fake = _install_fake_client(monkeypatch, FakeTranscription("hello", "ur", 1.5))
    audio_path = tmp_path / "fake.mp3"
    audio_path.write_bytes(b"fake-audio-bytes")

    model_backend.transcribe_file(str(audio_path), language_override="auto")
    assert "language" not in fake.audio.transcriptions.last_kwargs


def test_explicit_override_takes_precedence_over_configured_default(monkeypatch, tmp_path):
    fake = _install_fake_client(monkeypatch, FakeTranscription("bonjour", "fr", 1.0))
    monkeypatch.setattr(config, "WHISPER_LANGUAGE", "ur")
    audio_path = tmp_path / "fake.mp3"
    audio_path.write_bytes(b"fake-audio-bytes")

    model_backend.transcribe_file(str(audio_path), language_override="fr")
    assert fake.audio.transcriptions.last_kwargs["language"] == "fr"


def test_result_shape(monkeypatch, tmp_path):
    _install_fake_client(monkeypatch, FakeTranscription("hello world", "en", 2.5))
    audio_path = tmp_path / "fake.mp3"
    audio_path.write_bytes(b"fake-audio-bytes")

    result = model_backend.transcribe_file(str(audio_path), language_override="en")
    assert result == {"text": "hello world", "language": "en", "duration_seconds": 2.5}
