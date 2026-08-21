from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "game-session-service"
    redis_url: str = "redis://redis:6379/0"
    tick_rate_hz: int = 20
    room_id: str = "unassigned"


settings = Settings()
