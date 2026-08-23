# Part A: Design

## Architecture

The pipeline has two independently runnable stages. The extractor queries a `TweetSource` for
`#ChargeNow` in configurable UTC intervals, splitting large requests into time chunks. It exhausts
pagination and stores one combined source payload per successful chunk in an immutable S3 raw
layer under a run ID and extraction timestamp. PostgreSQL records each chunk's source interval,
object key, status, count, and error.

The loader reads explicitly selected S3 objects, normalizes each tweet to the required fields, and
computes a deterministic HMAC-SHA256 user identifier using a secret that is never stored with the
data. Operational usage selects keys from successful `pipeline_chunks` rows. Tweets are upserted
by source tweet ID, making reruns safe. Run and chunk metadata provide the operational audit trail.

## Robustness

### Empty results

An empty API result is successful. Its combined payload is stored in S3 and its chunk is recorded
with `record_count = 0`, distinguishing “queried with no matches” from skipped or failed work.
Loading an empty object is a successful no-op.

### API changes

`TweetSource` isolates provider-specific endpoints, parameters, and pagination. Additional fields
are ignored and missing optional collections receive safe defaults. Incompatible structural
changes, such as `data` no longer being a list, raise `SourceResponseError`; the chunk is recorded
as failed instead of producing misleading data.

### Source unavailability

Live calls have a 30-second timeout. Connection failures, timeouts, HTTP 429, and HTTP 5xx errors
retry up to four attempts with exponential backoff. Permanent HTTP 4xx request/authentication
errors fail immediately. Exhausted failures affect only their chunk; later chunks continue and the
overall run finishes as failed.

### Logging

The CLI emits UTC key-value logs to standard error using `LOG_LEVEL`. Events include run IDs,
chunk boundaries, S3 keys, counts, retries, and final statuses. Failed chunks include tracebacks.
Credentials, secrets, authorization headers, and tweet payloads are not logged.

### Fault tolerance and historical reprocessing

Any historical range can be submitted again. Each extraction has a new run ID and immutable S3
keys, while loading is idempotent because tweets are upserted by `tweet_id`.
`retry-failed-tweets <run-id>` creates a new run containing only failed intervals from the original
run. `Ctrl+C` finalizes the active run as failed before propagating the interruption.

### Scalability

Time chunks are processed by a bounded `ThreadPoolExecutor` with `EXTRACTION_WORKERS` workers.
Pagination exhausts results within each chunk, while the coordinator serializes PostgreSQL status
writes. S3 holds extracted payloads; PostgreSQL uses batch upserts and indexes on tweet time,
anonymized user ID, and failed-chunk status.

For much higher volume, the in-process executor should become distributed orchestration, database
connections should be pooled, loads should use a bulk-copy mechanism, and individual API pages
should stream to S3 rather than being combined in memory per chunk.

## Resolved exercise assumptions

- Mock/offline mode is the default and emits deterministic X-shaped data without X credentials.
- Live mode supports X API v2 recent and full-archive search, subject to account access.
- Requested timestamps must include a timezone; extraction normalizes chunks to UTC.
- A manually created local PostgreSQL database is the serving store, and AWS S3 stores extracted
  payloads. Docker and MinIO are not required.
- User IDs are pseudonymized deterministically with HMAC-SHA256 and an environment-supplied secret.

## Remaining production questions

1. What volume and request-rate limits should determine chunk size and worker count?
2. What S3 lifecycle and raw-data retention policies are required?
3. Should retry runs store an explicit database relationship to their original run?
4. Should loaded tweets retain `run_id` and `raw_key` lineage?
5. At higher volume, should each provider page be stored independently?
