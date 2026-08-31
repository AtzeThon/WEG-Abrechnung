"""Zentrale Konfiguration (12-Factor: Umgebungsvariablen, optional .env)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Projektwurzel (…/H:/Claude)
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WEG_",
        extra="ignore",
    )

    # --- Datenbank ------------------------------------------------------------
    # Pfad zur SQLite-Datei. Default: data/weg.db im Projektverzeichnis.
    database_path: Path = BASE_DIR / "data" / "weg.db"

    # --- Sicherheit --------------------------------------------------------- #
    # MUSS in Produktion gesetzt werden (WEG_SECRET_KEY). Der Default erlaubt
    # nur lokale Entwicklung und wird beim Start protokolliert.
    secret_key: str = "dev-only-insecure-secret-change-me"
    session_max_age: int = 60 * 60 * 12  # 12 Stunden
    # In Produktion (HTTPS über Caddy) auf true setzen: WEG_SECURE_COOKIES=true
    secure_cookies: bool = False

    # --- Anzeige ---------------------------------------------------------------
    locale: str = "de_DE"
    timezone: str = "Europe/Berlin"

    # --- Betrieb -------------------------------------------------------------- #
    debug: bool = False

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"

    @property
    def is_secret_key_insecure(self) -> bool:
        return self.secret_key == "dev-only-insecure-secret-change-me"

    def ensure_data_dir(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
