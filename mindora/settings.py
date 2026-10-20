from functools import cached_property
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    telegram_bot_token: SecretStr | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./mindora_dev.db",
        alias="DATABASE_URL",
    )
    admin_ids_raw: str = Field(default="", alias="ADMIN_IDS")
    app_environment: str = Field(default="development", alias="APP_ENV")
    port: int = Field(default=8080, alias="PORT")

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        value = value.strip()
        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
        parts = urlsplit(value)
        if parts.scheme == "postgresql+asyncpg":
            query = parse_qsl(parts.query, keep_blank_values=True)
            sslmode = next((item for key, item in query if key == "sslmode"), None)
            query = [(key, item) for key, item in query if key != "sslmode"]
            if sslmode is not None and not any(key == "ssl" for key, _ in query):
                query.append(("ssl", sslmode))
            value = urlunsplit(parts._replace(query=urlencode(query)))
        return value

    @model_validator(mode="after")
    def require_postgres_in_production(self):
        if self.app_environment.lower() in {"production", "prod"} and not self.database_url.startswith(
            "postgresql+asyncpg://"
        ):
            raise ValueError("Production deployments require a PostgreSQL DATABASE_URL.")
        if self.app_environment.lower() in {"production", "prod"} and not self.admin_ids:
            raise ValueError("Production deployments require at least one numeric ADMIN_IDS value.")
        return self

    @cached_property
    def admin_ids(self) -> frozenset[int]:
        ids: set[int] = set()
        for value in self.admin_ids_raw.split(","):
            candidate = value.strip()
            if not candidate:
                continue
            if not candidate.isdecimal() or int(candidate) <= 0:
                raise ValueError("ADMIN_IDS must contain positive numeric Telegram user IDs only.")
            ids.add(int(candidate))
        return frozenset(ids)


settings = Settings()


def is_authorized_admin(telegram_user_id: int | None, admin_ids: frozenset[int]) -> bool:
    """Authorization is based only on Telegram's immutable numeric user ID."""
    return telegram_user_id is not None and telegram_user_id in admin_ids
