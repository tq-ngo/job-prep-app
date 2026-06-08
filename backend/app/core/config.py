from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Job Prep Platform"
    API_V1_STR: str = "/api/v1"
    
    DATABASE_URL: str = Field(..., validation_alias="DATABASE_URL")
    REDIS_URL: str = Field(..., validation_alias="REDIS_URL")
    GEMINI_API_KEY: str = Field(..., validation_alias="GEMINI_API_KEY")

    SECRET_KEY: str = Field("DEVELOPMENT_SECRET_KEY_REPLACE_IN_PRODUCTION", validation_alias="SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()