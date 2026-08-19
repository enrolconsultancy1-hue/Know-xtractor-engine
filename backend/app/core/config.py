"""Application configuration via environment variables (pydantic-settings)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """KNOX settings. All values are overridable through environment variables."""

    model_config = SettingsConfigDict(env_prefix="KNOX_", env_file=".env", extra="ignore")

    app_name: str = "KNOX"
    version: str = "0.1.0"
    api_prefix: str = "/api"
    environment: str = "development"  # development | production

    # Observability (Phase 4)
    log_format: str = "text"           # text | json
    log_level: str = "INFO"
    stale_workspace_max_age_days: int = 7

    # Rate limiting (Phase 7); 0 disables.
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # Auth (Phase 2). token = shared bearer key; users/JWT is a future extension.
    auth_mode: str = "none"  # none | token
    api_key: str | None = None

    # Queue (Phase 3). inprocess (dev) | rq (Redis-backed worker pool).
    queue_backend: str = "inprocess"
    redis_url: str = "redis://localhost:6379/0"

    # Storage
    data_dir: Path = Path("data")
    workspace_dir: Path = Path("analysis_workspace")
    packages_dir: Path = Path("knowledge_packages")
    exports_dir: Path = Path("exports")
    database_url: str = "sqlite:///./data/knox.db"

    # Analysis limits (security + resource controls)
    max_file_size_bytes: int = 2 * 1024 * 1024  # 2 MB per text file
    max_files_per_analysis: int = 20_000
    max_analysis_depth: int = 3  # 1..3; controls how much deep static analysis is done
    clone_timeout_seconds: int = 600
    analysis_timeout_seconds: int = 3600
    max_workers: int = 4  # parallel analysis workers

    # Git clone security
    allow_network_clone: bool = True

    # AI (optional). Leave provider unset to run fully deterministic.
    ai_provider: str = "none"  # none | openai | anthropic | gemini
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None

    # Prompt compilation (mission: one budgeted prompt for a frontier model).
    prompt_max_tokens: int = 50000

    # Logic capture (opt-in source-of-record for function bodies). OFF by
    # default: it deliberately re-materializes verbatim source into the
    # knowledge package. Bounds keep the package size predictable.
    logic_capture_enabled: bool = False
    logic_capture_max_functions: int = 200
    logic_capture_max_lines_per_function: int = 60
    logic_capture_include_tests: bool = False

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    def ensure_dirs(self) -> None:
        """Create runtime directories if missing."""
        for d in (self.data_dir, self.workspace_dir, self.packages_dir, self.exports_dir):
            Path(d).mkdir(parents=True, exist_ok=True)

    def validate_production(self) -> list[str]:
        """Return a list of production-config problems (empty when valid).

        In production we fail fast on settings that would be unsafe or
        silently lossy (SQLite, wildcard CORS).
        """
        problems: list[str] = []
        if self.environment != "production":
            return problems
        if self.database_url.startswith("sqlite"):
            problems.append("KNOX_DATABASE_URL must point at a non-SQLite database in production")
        if "*" in self.cors_origins:
            problems.append("KNOX_CORS_ORIGINS must be an explicit allowlist (no '*') in production")
        if self.auth_mode == "token" and not self.api_key:
            problems.append("KNOX_AUTH_MODE=token requires KNOX_API_KEY to be set")
        return problems


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings
