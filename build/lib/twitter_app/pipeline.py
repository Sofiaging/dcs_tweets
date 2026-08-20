import logging
import uuid
from datetime import datetime, timedelta, timezone

from .db import PostgresRepository
from .source import TweetSource
from .storage import S3RawStore
from .transform import normalize_payload

logger = logging.getLogger(__name__)


def extract(start: datetime, end: datetime, chunk_hours: int, source: TweetSource, store: S3RawStore, repository: PostgresRepository) -> str:
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("start and end must be timezone-aware, with start before end")
    run_id = str(uuid.uuid4())
    repository.start_run(run_id, start, end)
    current = start.astimezone(timezone.utc)
    overall_status = "succeeded"
    while current < end:
        chunk_end = min(current + timedelta(hours=chunk_hours), end)
        try:
            payload = source.search(current, chunk_end)
            key = store.put_immutable(run_id, current, chunk_end, payload)
            repository.record_chunk(run_id, current, chunk_end, key, "succeeded", len(payload.get("data", [])))
        except Exception as error:
            overall_status = "failed"
            logger.exception("Chunk failed: %s - %s", current, chunk_end)
            repository.record_chunk(run_id, current, chunk_end, None, "failed", error=str(error))
        current = chunk_end
    repository.finish_run(run_id, overall_status)
    return run_id


def load(run_id: str, keys: list[str], store: S3RawStore, repository: PostgresRepository, secret: str) -> int:
    loaded = 0
    for key in keys:
        envelope = store.read_json(key)
        tweets = normalize_payload(envelope, secret)
        repository.upsert_tweets(tweets)
        loaded += len(tweets)
    return loaded
