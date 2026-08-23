import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required setting: {name}. Set it in .env.")
    return value


def boolean_setting(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"{name} must be true or false")


@dataclass(frozen=True)
class Settings:
    database_url: str
    s3_endpoint_url: str | None
    s3_region: str
    s3_bucket: str
    aws_profile: str
    x_bearer_token: str
    anonymization_secret: str
    chunk_hours: int
    api_page_size: int
    x_use_full_archive: bool
    x_use_mock_data: bool
    log_level: str
    extraction_workers: int

    @classmethod
    def from_env(cls) -> "Settings":
        use_mock_data = boolean_setting("X_USE_MOCK_DATA", default=True)
        bearer_token = os.getenv("X_BEARER_TOKEN", "").strip()
        if not use_mock_data and not bearer_token:
            raise ValueError("Missing required setting: X_BEARER_TOKEN. Set it in .env.")
        return cls(
            database_url=required_setting("DATABASE_URL"),
            s3_endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
            s3_region=os.getenv("S3_REGION", "us-east-1"),
            s3_bucket=os.getenv("S3_BUCKET", "twitter-raw"),
            aws_profile=os.getenv("AWS_PROFILE", "default"),
            x_bearer_token=bearer_token,
            anonymization_secret=required_setting("ANONYMIZATION_SECRET"),
            chunk_hours=int(os.getenv("CHUNK_HOURS", "1")),
            api_page_size=int(os.getenv("API_PAGE_SIZE", "100")),
            x_use_full_archive=boolean_setting("X_USE_FULL_ARCHIVE"),
            x_use_mock_data=use_mock_data,
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            extraction_workers=int(os.getenv("EXTRACTION_WORKERS", "4")),
        )
