# ChargeNow Twitter Pipeline

A replayable two-stage pipeline for tweets matching `#ChargeNow`.

## Architecture

1. `extract` queries the configured source in UTC chunks and writes the exact response to an immutable S3 key.
2. `load` reads raw envelopes from S3, validates and normalizes records, deterministically anonymizes user IDs with HMAC-SHA256, and upserts tweets into PostgreSQL.
3. PostgreSQL stores pipeline runs and chunks so failures are visible and independent chunks can be retried.

The source API is deliberately isolated behind `TweetSource`. The default implementation uses the X API v2 recent-search endpoint, but a fixture source can be supplied for local development and tests.

## Quick start

```bash
cp .env.example .env
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
docker compose up -d postgres minio
python -m twitter_app.cli init-db
```

Set `X_BEARER_TOKEN`, `ANONYMIZATION_SECRET`, and storage/database settings in `.env` before extraction. Local MinIO uses the S3 endpoint in `.env.example`.

```bash
twitter-pipeline extract --start 2026-01-01T00:00:00Z --end 2026-01-02T00:00:00Z
twitter-pipeline load --run-id <run-id>
```

For a deterministic local run, pass a JSON fixture to the Python API used by the tests or implement another `TweetSource` adapter.

## Development

```bash
pytest
ruff check .
```

See [DESIGN.md](DESIGN.md) for assumptions and open questions from Part A.
