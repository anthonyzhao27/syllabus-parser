from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

# Default CORS origins used in development. In production the deployer MUST
# override allowed_origins (via the ALLOWED_ORIGINS env var) so the app does
# not accidentally ship with a localhost-only CORS policy.
DEFAULT_ALLOWED_ORIGINS = ["http://localhost:3000"]

# Secrets the app cannot function without in production. If any is empty when
# ENVIRONMENT=production the app refuses to start (fail fast) rather than
# booting silently broken.
_REQUIRED_SECRETS = (
    "openai_api_key",
    "supabase_url",
    "supabase_anon_key",
    "supabase_service_role_key",
)


class Settings(BaseSettings):
    environment: str = "development"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    vision_model: str = "gpt-4o"
    vision_dpi: int = 150
    vision_detail: str = "low"
    vision_max_pages: int = 20
    extraction_cache_enabled: bool = True
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    max_file_size_mb: int = 10
    allowed_origins: list[str] = list(DEFAULT_ALLOWED_ORIGINS)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @model_validator(mode="after")
    def _require_production_config(self) -> "Settings":
        """In production, fail fast on missing secrets / unsafe CORS.

        Development keeps the permissive empty / localhost defaults so the app
        can boot for local work without any secrets configured.
        """
        if not self.is_production:
            return self

        missing = [
            name
            for name in _REQUIRED_SECRETS
            if not (getattr(self, name) or "").strip()
        ]
        if missing:
            raise ValueError(
                "Missing required secrets in production environment: "
                + ", ".join(missing)
                + ". Set them via environment variables (see "
                "backend/.env.example)."
            )

        if self.allowed_origins == DEFAULT_ALLOWED_ORIGINS:
            raise ValueError(
                "allowed_origins is still the localhost default in production. "
                "Set ALLOWED_ORIGINS to your real deployment origin(s) "
                "(comma-separated)."
            )

        return self


settings = Settings()
