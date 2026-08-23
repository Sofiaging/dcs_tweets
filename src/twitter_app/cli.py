import logging
import time
from datetime import datetime

import typer

from .config import Settings
from .db import PostgresRepository
from .pipeline import extract, load
from .source import MockTweetSource, XApiSource
from .storage import S3RawStore

app = typer.Typer(help="Extract and load #ChargeNow tweets.")


def configure_logging(level: str) -> None:
    numeric_level = getattr(logging, level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid LOG_LEVEL: {level}")
    logging.Formatter.converter = time.gmtime
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)sZ level=%(levelname)s logger=%(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        force=True,
    )
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def configured_settings() -> Settings:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    return settings


def parse_timestamp(value: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise typer.BadParameter("use ISO-8601, for example 2026-01-01T00:00:00+00:00") from error
    if timestamp.tzinfo is None:
        raise typer.BadParameter("timestamp must include a timezone, for example +00:00")
    return timestamp


@app.command()
def init_db() -> None:
    settings = configured_settings()
    logging.getLogger(__name__).info("event=database_initialization_started")
    PostgresRepository(settings.database_url).initialize()
    logging.getLogger(__name__).info("event=database_initialization_succeeded")
    typer.echo("Database schema initialized")


@app.command()
def extract_tweets(
    start: str = typer.Option(..., "--start"),
    end: str = typer.Option(..., "--end"),
) -> None:
    settings = configured_settings()
    start_timestamp = parse_timestamp(start)
    end_timestamp = parse_timestamp(end)
    source = (
        MockTweetSource()
        if settings.x_use_mock_data
        else XApiSource(
            settings.x_bearer_token,
            settings.api_page_size,
            settings.x_use_full_archive,
        )
    )
    run_id = extract(
        start_timestamp,
        end_timestamp,
        settings.chunk_hours,
        source,
        S3RawStore(
            settings.s3_bucket,
            settings.s3_endpoint_url,
            settings.s3_region,
            settings.aws_profile,
        ),
        PostgresRepository(settings.database_url),
    )
    typer.echo(run_id)


@app.command()
def load_tweets(run_id: str, keys: list[str] = typer.Option(..., "--key")) -> None:
    settings = configured_settings()
    count = load(
        run_id,
        keys,
        S3RawStore(settings.s3_bucket, settings.s3_endpoint_url, settings.s3_region, settings.aws_profile),
        PostgresRepository(settings.database_url),
        settings.anonymization_secret,
    )
    typer.echo(f"Loaded {count} tweets")


if __name__ == "__main__":
    app()
