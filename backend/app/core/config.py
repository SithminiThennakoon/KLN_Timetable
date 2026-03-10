from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()


def _default_sqlite_url() -> str:
    db_path = Path(__file__).resolve().parents[2] / "data" / "kln_timetable.db"
    return f"sqlite:///{db_path}"


def _parse_csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    PROJECT_NAME: str = "KLN Timetable API"
    PROJECT_VERSION: str = "1.0.0"

    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-this")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

    APP_ENV: str = os.getenv("APP_ENV", "development")
    DATABASE_URL: str = os.getenv("DATABASE_URL", _default_sqlite_url())
    RESET_DB: bool = os.getenv("RESET_DB", "0") == "1"
    CORS_ALLOWED_ORIGINS: list[str] = _parse_csv_env(
        "CORS_ALLOWED_ORIGINS",
        [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
    )

settings = Settings()
