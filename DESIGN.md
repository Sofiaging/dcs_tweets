# Part A: Design

## Architecture

The pipeline has two independently runnable stages. The extractor queries an X API adapter for `#ChargeNow` in configurable UTC intervals, splitting large requests into time chunks. Each successful response is stored unchanged in an immutable S3 raw layer under a run ID and extraction timestamp. A manifest records each chunk, its source interval, object key, status, counts, and errors.

The loader reads only successful raw objects. It validates the provider envelope with tolerant field access, normalizes each tweet to the required fields, and computes a deterministic HMAC-SHA256 user identifier using a secret that is never stored with the data. Tweets are upserted by source tweet ID, making reruns safe. Run and chunk metadata are persisted in PostgreSQL, which also provides the operational audit trail.

Transient API failures retry with exponential backoff. A failed chunk is marked independently, so a later retry does not repeat successful chunks. Empty results are valid successful chunks. Source payloads remain available for replay if transformation rules change.

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
