from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    football_data_token: str
    database_url: str = "sqlite:///data/ucl.db"


settings = Settings()