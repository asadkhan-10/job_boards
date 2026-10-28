# app/config.py
from pydantic_settings import BaseSettings  # type: ignore


class Settings(BaseSettings):
    database_hostname: str
    database_port: int
    database_username: str
    database_password: str
    database_name: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    redis_url: str = "redis://localhost:6379/0"
    healthcheck_url: str = ""
    voyage_api_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    class Config:
        env_file = ".env"


settings = Settings()  # type: ignore