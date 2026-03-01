import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration — values pulled from .env file."""

    # Core
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Database
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "DATABASE_URL", "sqlite:///smart_campus.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "jwt-super-secret")
    JWT_ACCESS_TOKEN_EXPIRES: int = int(os.getenv("JWT_EXPIRES_HOURS", "24")) * 3600

    # CORS
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

    # AI / Model settings
    AI_CONGESTION_THRESHOLD: int = int(os.getenv("AI_CONGESTION_THRESHOLD", "200"))
    AI_CRITICAL_THRESHOLD: int = int(os.getenv("AI_CRITICAL_THRESHOLD", "350"))

    # Capacity management
    DEFAULT_GLOBAL_CAPACITY: int = int(os.getenv("DEFAULT_GLOBAL_CAPACITY", "50"))
    DEFAULT_WARNING_THRESHOLD: float = float(os.getenv("DEFAULT_WARNING_THRESHOLD", "0.7"))  # 70%
    DEFAULT_CRITICAL_THRESHOLD: float = float(os.getenv("DEFAULT_CRITICAL_THRESHOLD", "0.9"))  # 90%

    # API Authentication
    API_KEY: str = os.getenv("API_KEY", "")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
