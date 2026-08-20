import logging
from datetime import datetime

import typer

from .config import Settings
from .db import PostgresRepository
from .pipeline import extract, load
from .source import XApiSource
from .storage import S3RawStore

app = typer.Typer(help="Extract and load #ChargeNow tweets.")


@app.command()
def init_db() -> None:
    settings = Settings.from_env()
    PostgresRepository(settings.database_url).initialize()
    typer.echo("Database schema initialized")


@app.command()
def extract_tweets(start: datetime, end: datetime) -> None:
    settings = Settings.from_env()
    run_id = extract(
        start,
        end,
        settings.chunk_hours,
        XApiSource(settings.x_bearer_token, settings.api_page_size),
        S3RawStore(settings.s3_bucket, settings.s3_endpoint_url, settings.s3_region, settings.aws_profile),
        PostgresRepository(settings.database_url),
    )
    typer.echo(run_id)


@app.command()
def load_tweets(run_id: str, keys: list[str] = typer.Option(..., "--key")) -> None:
    settings = Settings.from_env()
    count = load(
        run_id,
        keys,
        S3RawStore(settings.s3_bucket, settings.s3_endpoint_url, settings.s3_region, settings.aws_profile),
        PostgresRepository(settings.database_url),
        settings.anonymization_secret,
    )
    typer.echo(f"Loaded {count} tweets")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app()
