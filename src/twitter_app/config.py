from dataclasses import dataclass
import os


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

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ["DATABASE_URL"],
            s3_endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            s3_region=os.getenv("S3_REGION", "us-east-1"),
            s3_bucket=os.getenv("S3_BUCKET", "twitter-raw"),
            aws_profile=os.getenv("AWS_PROFILE", "default"),
            x_bearer_token=os.environ["X_BEARER_TOKEN"],
            anonymization_secret=os.environ["ANONYMIZATION_SECRET"],
            chunk_hours=int(os.getenv("CHUNK_HOURS", "1")),
            api_page_size=int(os.getenv("API_PAGE_SIZE", "100")),
        )
