# ChargeNow Twitter Pipeline

A replayable two-stage pipeline for tweets matching `#ChargeNow`.

## Architecture

1. `extract` queries the configured source in UTC chunks and writes the exact response to an immutable S3 key.
2. `load` reads raw envelopes from S3, validates and normalizes records, deterministically anonymizes user IDs with HMAC-SHA256, and upserts tweets into PostgreSQL.
3. PostgreSQL stores pipeline runs and chunks so failures are visible and independent chunks can be retried.

The source is isolated behind `TweetSource`. Offline mode uses deterministic simulated X-shaped
responses and requires no X credentials. Live mode supports the X API v2 recent-search and
full-archive endpoints.

## Prerequisites

- Python 3.11 or newer.
- A PostgreSQL server running locally (not in Docker).
- An AWS profile with access to the configured S3 bucket.

Create the local database and user once from a PostgreSQL administrator session, replacing the
placeholder with your own password:

```sql
CREATE USER charge_now_user WITH PASSWORD '<local-password>';
CREATE DATABASE chargenow_tweets OWNER charge_now_user;
```

## Quick start

```bash
cp .env.example .env
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
twitter-pipeline init-db
```

Before `init-db`, edit `.env` so `DATABASE_URL` contains the local database password. Keep
`S3_ENDPOINT_URL` empty to use AWS S3, and set `S3_REGION`, `S3_BUCKET`, and `AWS_PROFILE` to the
existing AWS resources. The application creates the tables, but it does not create the PostgreSQL
database, AWS profile, or S3 bucket.

Mock mode is enabled by default in `.env.example`, so extraction does not require X credentials:

```dotenv
X_USE_MOCK_DATA=true
X_USE_FULL_ARCHIVE=false
```

`MockTweetSource` deterministically generates one X-shaped tweet per configured time chunk. To
call X instead, set `X_USE_MOCK_DATA=false` and provide `X_BEARER_TOKEN`. Set
`X_USE_FULL_ARCHIVE=true` to select the full-archive endpoint; otherwise the recent-search endpoint
is used.

```bash
twitter-pipeline extract-tweets --start 2026-01-01T00:00:00Z --end 2026-01-02T00:00:00Z
twitter-pipeline load-tweets <run-id> --key '<s3-object-key>'
twitter-pipeline retry-failed-tweets <failed-run-id>
```

Extraction writes raw objects to the configured S3 bucket and records their keys in
`pipeline_chunks`. Loading reads the selected keys, normalizes and anonymizes the tweets, and
upserts them into the `tweets` table.

Historical ranges can be submitted again safely: every extraction receives a new run ID and new
immutable S3 keys, while loading upserts by `tweet_id`. `retry-failed-tweets` creates a new run for
only the failed intervals of an earlier run, leaving its successful chunks untouched.

## Development

```bash
pytest
ruff check .
```

See [DESIGN.md](DESIGN.md) for assumptions and open questions from Part A.
