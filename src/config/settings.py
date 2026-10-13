from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .paths import PROJECT_ROOT


class Settings(BaseSettings):
    PROJECT_NAME: str = "Whisper STT Service"
    VERSION: str = "1.0.0"
    ENV: str = Field(default="development", validation_alias="APP_ENV")

    RAW_LOG_DIR: str = Field(default="logs", validation_alias="LOG_DIR")
    RAW_DATA_DIR: str = Field(default="data", validation_alias="DATA_DIR")

    API_HOST: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    API_PORT: int = Field(default=8020, validation_alias="API_PORT")

    API_KEY: str = Field(default="sk-whisper-bn-secret", validation_alias="API_KEY")

    DEFAULT_MODEL: str = Field(default="shhossain/whisper-base-bn", validation_alias="DEFAULT_MODEL")
    DEFAULT_LANGUAGE: str = Field(default="bn", validation_alias="DEFAULT_LANGUAGE")
    NOISE_REDUCTION_DEFAULT: bool = Field(default=True, validation_alias="NOISE_REDUCTION_DEFAULT")

    def _resolve(self, val: str) -> Path:
        val = val.strip()
        if val.startswith("/."):
            val = "~/" + val[2:] if val.startswith("/./") else "~/" + val[1:]
        if val.startswith(".") and not val.startswith("./") and not val.startswith("../"):
            val = "~/" + val
        p = Path(val).expanduser()
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def LOG_DIR(self) -> Path:
        return self._resolve(self.RAW_LOG_DIR)

    @property
    def DATA_DIR(self) -> Path:
        return self._resolve(self.RAW_DATA_DIR)

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.ENV.lower() == "development"

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


Settings = Settings()