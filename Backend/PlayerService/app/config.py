from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "player-service"
    database_url: str = "postgresql+psycopg2://spacerace:spacerace@postgres:5432/spacerace"


settings = Settings()
