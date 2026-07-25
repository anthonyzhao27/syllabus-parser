"""Tests for fail-fast settings validation."""

import pytest

from app.config import DEFAULT_ALLOWED_ORIGINS, Settings


def _production_kwargs(**overrides):
    """Fully-populated production settings; override fields to break them."""
    base = {
        "environment": "production",
        "openai_api_key": "sk-test",
        "supabase_url": "https://example.supabase.co",
        "supabase_anon_key": "anon-key",
        "allowed_origins": "https://syllabuddy.example.com",
    }
    base.update(overrides)
    return base


def test_development_tolerates_empty_secrets():
    """Development keeps permissive empty / localhost defaults."""
    settings = Settings(_env_file=None, environment="development")

    assert settings.openai_api_key == ""
    assert settings.supabase_url == ""
    assert settings.allowed_origins == DEFAULT_ALLOWED_ORIGINS
    assert settings.is_production is False


@pytest.mark.parametrize(
    "missing_field",
    [
        "openai_api_key",
        "supabase_url",
        "supabase_anon_key",
    ],
)
def test_production_missing_secret_raises(missing_field):
    """Each critical secret must be present in production."""
    kwargs = _production_kwargs(**{missing_field: ""})

    with pytest.raises(ValueError) as excinfo:
        Settings(_env_file=None, **kwargs)

    assert missing_field in str(excinfo.value)


def test_production_whitespace_secret_raises():
    """Whitespace-only secrets are treated as missing in production."""
    kwargs = _production_kwargs(openai_api_key="   ")

    with pytest.raises(ValueError):
        Settings(_env_file=None, **kwargs)


def test_production_localhost_origins_raises():
    """Production must override the localhost CORS default."""
    kwargs = _production_kwargs(allowed_origins="http://localhost:3000")

    with pytest.raises(ValueError) as excinfo:
        Settings(_env_file=None, **kwargs)

    assert "allowed_origins" in str(excinfo.value)


def test_production_fully_configured_succeeds():
    """A complete production config boots without error."""
    settings = Settings(_env_file=None, **_production_kwargs())

    assert settings.is_production is True
    assert settings.allowed_origins == ["https://syllabuddy.example.com"]


def test_allowed_origins_parses_comma_separated_env(monkeypatch):
    """ALLOWED_ORIGINS is a plain comma-separated env string, not JSON.

    Regression: without NoDecode, pydantic-settings JSON-decodes the list field
    from the env source and raises SettingsError on a plain string.
    """
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.com, https://b.com")
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == ["https://a.com", "https://b.com"]


def test_allowed_origins_single_env_value(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://only.example.com")
    settings = Settings(_env_file=None)
    assert settings.allowed_origins == ["https://only.example.com"]
