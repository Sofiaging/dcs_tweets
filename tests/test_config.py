import pytest

from twitter_app.config import Settings


def test_mock_mode_does_not_require_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("X_USE_MOCK_DATA", "true")
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    monkeypatch.setenv("ANONYMIZATION_SECRET", "secret")

    assert Settings.from_env().x_bearer_token == ""


def test_live_mode_requires_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("X_USE_MOCK_DATA", "false")
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    monkeypatch.setenv("ANONYMIZATION_SECRET", "secret")

    with pytest.raises(ValueError, match="X_BEARER_TOKEN"):
        Settings.from_env()
