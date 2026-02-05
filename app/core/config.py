from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    OPENAI_API_KEY: str
    
    # Hardcoded Admin Settings
    ADMIN_EMAIL: str = "admin@yourdomain.com"
    ADMIN_NAME: str = "System Admin"
    ADMIN_DEFAULT_PASSWORD: str = "admin123"
    
    # JWT Settings
    JWT_SECRET: str = "your-super-secret-key-change-in-production"
    JWT_EXPIRATION_HOURS: int = 24

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
