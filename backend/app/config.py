import os
from pydantic_settings import BaseSettings

WEAK_SECRETS = {"", "CHANGE_ME", "change-me", "change_me", "your-secret-here"}


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "postgresql+asyncpg://aiuser:aipass@db:5432/aiassistant"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # Auth
    device_secret: str = "CHANGE_ME"

    # App environment: "development" or "production"
    app_env: str = "production"

    # Memory
    memory_retrieval_count: int = 5

    model_config = {"env_file": ".env"}


settings = Settings()

# Enforce strong device_secret in production
if settings.app_env != "development" and settings.device_secret in WEAK_SECRETS:
    raise RuntimeError(
        "DEVICE_SECRET 不能使用默认值！请在 .env 中设置一个强随机字符串。\n"
        "开发环境可设置 APP_ENV=development 跳过此检查。"
    )
