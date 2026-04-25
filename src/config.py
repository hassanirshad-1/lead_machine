"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Google API (needed for enrichment in Phase 2)
    google_places_api_key: str = ""
    serper_api_key: str = ""

    # Apify (LinkedIn profile scraping)
    apify_api_token: str = ""

    # Database — SQLite by default (zero setup), switch to PostgreSQL for production
    database_url: str = "sqlite+aiosqlite:///./lead_machine.db"

    # Application
    debug: bool = True
    environment: str = "development"

    # Discovery defaults
    max_pages_per_query: int = 3  # Google caps at 60 results (20/page × 3 pages)
    places_api_qps: int = 10  # queries per second limit

    # Grid scanning — breaks the 60-lead-per-query cap
    grid_radius_meters: int = 5000  # radius for each grid circle
    grid_size: int = 5  # 5×5 = 25 sub-queries per city


settings = Settings()
