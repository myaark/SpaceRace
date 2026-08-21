from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "matchmaking-service"
    redis_url: str = "redis://redis:6379/0"
    min_players_per_match: int = 2
    max_players_per_match: int = 10


settings = Settings()
