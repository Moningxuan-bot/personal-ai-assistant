from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "postgresql+asyncpg://aiuser:aipass@db:5432/aiassistant"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # Auth
    device_secret: str = "CHANGE_ME"

    # Memory
    memory_retrieval_count: int = 5

    model_config = {"env_file": ".env"}


settings = Settings()
