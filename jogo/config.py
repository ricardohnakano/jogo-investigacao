from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Jogo Investigativo"
    host: str = "0.0.0.0"
    port: int = 8000
    data_dir: Path = Path("data")
    db_path: Path = Path("data/game.db")
    anthropic_api_key: str = ""
    openai_api_key: str = ""


settings = Settings()
