# Part A: Design

## Architecture

The pipeline has two independently runnable stages. The extractor queries an X API adapter for `#ChargeNow` in configurable UTC intervals, splitting large requests into time chunks. Each successful response is stored unchanged in an immutable S3 raw layer under a run ID and extraction timestamp. A manifest records each chunk, its source interval, object key, status, counts, and errors.

The loader reads only successful raw objects. It validates the provider envelope with tolerant field access, normalizes each tweet to the required fields, and computes a deterministic HMAC-SHA256 user identifier using a secret that is never stored with the data. Tweets are upserted by source tweet ID, making reruns safe. Run and chunk metadata are persisted in PostgreSQL, which also provides the operational audit trail.

Transient API failures retry with exponential backoff. A failed chunk is marked independently, so a later retry does not repeat successful chunks. Empty results are valid successful chunks. Source payloads remain available for replay if transformation rules change.

## Robustness

### Empty results

An API response containing no tweets is a valid result, not an error. The extractor stores the empty
payload in S3 and records the chunk as `succeeded` with `record_count = 0`. This proves that the
interval was queried and distinguishes an empty interval from a skipped or failed interval. If an
empty raw object is passed to the loader, normalization returns no records and the load completes
successfully without writing to the `tweets` table.

### API changes

`TweetSource` isolates the pipeline from provider-specific endpoints, request parameters, and
pagination. `XApiSource` converts every page into one stable internal `data`/`includes`/`meta`
shape. Additional provider fields are ignored, while missing optional collections are treated as
empty. The transformer also uses tolerant access and defaults for optional tweet and user fields.

If X changes a structural contract that the adapter depends on—for example, returning an object
instead of a list for `data`, or changing the type of `meta.next_token`—the adapter raises a
descriptive `SourceResponseError`. The pipeline then records that chunk as failed rather than
storing or loading a misleading partial result. Tests cover both additive and incompatible schema
changes.

### Source unavailability

Live X requests have a 30-second timeout and retry temporary failures up to four attempts with
exponential backoff, capped at 30 seconds between attempts. Connection failures, timeouts, HTTP 429
rate limits, and HTTP 5xx provider failures are retryable. Permanent request and authentication
errors such as HTTP 400, 401, and 403 fail immediately because repeating the same request cannot
resolve them.

If all attempts fail, extraction records that date chunk as `failed`, including the error, and
continues with later independent chunks. The overall pipeline run finishes as `failed`, while
successful chunks and their raw S3 objects remain intact. A source outage therefore does not erase
completed work or prevent the pipeline from recording exactly which intervals need reprocessing.

### Logging

The CLI configures UTC application logs using the `LOG_LEVEL` environment setting. Logs use a
consistent key-value format and include event names plus operational identifiers such as `run_id`,
chunk boundaries, S3 keys, record counts, source type, and final status. Extraction and loading log
their start, per-chunk or per-object progress, completion, and failures. Retry attempts are emitted
at warning level, while failed chunks include a traceback.

Secrets, authorization headers, anonymization keys, and tweet payloads are never written to logs.
Verbose `botocore` and `httpx` informational logs are suppressed so application lifecycle events
remain readable. `LOG_LEVEL=DEBUG`, `INFO`, `WARNING`, or `ERROR` can adjust verbosity without a
code change.

### Fault tolerance and historical reprocessing

Any timezone-aware historical date range can be extracted again. Each attempt receives a new run
ID and writes to new immutable S3 keys, so reprocessing never overwrites the earlier raw evidence.
Loading is idempotent because PostgreSQL upserts records by `tweet_id`.

For partial failures, `retry-failed-tweets <run-id>` reads only failed chunk boundaries from
`pipeline_chunks` and creates a new extraction run containing those intervals. Successful chunks
from the original run are not requested again. The original run remains unchanged as an audit
record, and the retry has its own run and chunk statuses.

Run-level interruption handling catches termination such as `Ctrl+C`, finalizes the run as
`failed`, records the interruption type, and re-raises it so the process still exits immediately.
This prevents interrupted executions from remaining indefinitely marked as `running`.

### Scalability

Time-based chunking makes extraction work independently partitionable. A bounded thread pool runs
up to `EXTRACTION_WORKERS` chunks concurrently, while each chunk follows all X pagination tokens.
The worker count is configurable so throughput can be balanced against X rate limits and local
resource constraints. PostgreSQL chunk-status writes remain serialized in the coordinator, and
each repository operation uses its own short-lived connection.

Raw responses are written directly to S3 instead of PostgreSQL, allowing storage to grow
independently from the serving database. Tweet loads use batch `executemany` operations and
idempotent upserts. Indexes on tweet time, anonymized user ID, and failed chunk status support the
main serving and operational queries.

This design scales reasonably for the take-home workload, but very high-volume production use
would replace the in-process thread pool with a distributed queue or orchestrator, use a database
connection pool and bulk loading, and stream individual API pages to S3 instead of combining a
whole chunk in memory.

## Assumptions

- Mock/offline mode is the default and does not require X credentials. Live mode can select X API
  v2 recent or full-archive search; historical availability depends on the account tier.
- Requested timestamps are UTC and must include a timezone.
- A manually created local PostgreSQL database is the serving store, and AWS S3 is the immutable
  source of truth for raw responses. Docker and MinIO are not required.
- A deterministic HMAC is acceptable for pseudonymization; the secret is supplied through environment configuration.
- Tweet fields are requested from the API where available: author location, public metrics, created time, entities, and referenced tweets.

## Open questions

1. Which X/Twitter API tier or alternate source and credentials will be provided?
2. Is historical search required beyond the API tier's retention window?
3. What volume and request-rate limits should drive chunk size and concurrency?
4. Are there retention, key rotation, or deletion requirements for the pseudonymization secret?
5. Should location be the profile location string or a geocoded field?
