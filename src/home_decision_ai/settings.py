from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = Field(default="home-decision-ai", alias="HOME_DECISION_AI_APP_NAME")
    environment: str = Field(default="development", alias="HOME_DECISION_AI_ENV")
    config_dir: str = Field(default="config", alias="HOME_DECISION_AI_CONFIG_DIR")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    notion_api_key: str | None = Field(default=None, alias="NOTION_API_KEY")
    notion_parent_page_id: str | None = Field(default=None, alias="NOTION_PARENT_PAGE_ID")
    notion_watchlist_database_id: str | None = Field(default=None, alias="NOTION_WATCHLIST_DATABASE_ID")
    notion_top5_database_id: str | None = Field(default=None, alias="NOTION_TOP5_DATABASE_ID")
    notion_events_database_id: str | None = Field(default=None, alias="NOTION_EVENTS_DATABASE_ID")
    notion_price_queue_database_id: str | None = Field(
        default=None,
        alias="NOTION_PRICE_QUEUE_DATABASE_ID",
    )
    notion_daily_database_id: str | None = Field(default=None, alias="NOTION_DAILY_DATABASE_ID")
    notion_weekly_database_id: str | None = Field(default=None, alias="NOTION_WEEKLY_DATABASE_ID")
    notion_alert_database_id: str | None = Field(default=None, alias="NOTION_ALERT_DATABASE_ID")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    public_data_api_key: str | None = Field(default=None, alias="PUBLIC_DATA_API_KEY")
    bok_ecos_api_key: str | None = Field(default=None, alias="BOK_ECOS_API_KEY")
    naver_client_id: str | None = Field(default=None, alias="NAVER_CLIENT_ID")
    naver_client_secret: str | None = Field(default=None, alias="NAVER_CLIENT_SECRET")
    kakao_rest_api_key: str | None = Field(default=None, alias="KAKAO_REST_API_KEY")

    @property
    def is_database_enabled(self) -> bool:
        return bool(self.database_url)

    @property
    def is_notion_enabled(self) -> bool:
        return bool(self.notion_api_key and self.notion_parent_page_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
