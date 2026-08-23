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
    logger.info(
        "event=extraction_started run_id=%s start=%s end=%s chunk_hours=%s source=%s",
        run_id,
        start.isoformat(),
        end.isoformat(),
        chunk_hours,
        type(source).__name__,
    )
    current = start.astimezone(timezone.utc)
    overall_status = "succeeded"
    while current < end:
        chunk_end = min(current + timedelta(hours=chunk_hours), end)
        logger.info(
            "event=chunk_started run_id=%s chunk_start=%s chunk_end=%s",
            run_id,
            current.isoformat(),
            chunk_end.isoformat(),
        )
        try:
            payload = source.search(current, chunk_end)
            key = store.put_immutable(run_id, current, chunk_end, payload)
            record_count = len(payload.get("data", []))
            repository.record_chunk(
                run_id, current, chunk_end, key, "succeeded", record_count
            )
            logger.info(
                "event=chunk_succeeded run_id=%s chunk_start=%s chunk_end=%s "
                "record_count=%s raw_key=%s",
                run_id,
                current.isoformat(),
                chunk_end.isoformat(),
                record_count,
                key,
            )
        except Exception as error:
            overall_status = "failed"
            logger.exception(
                "event=chunk_failed run_id=%s chunk_start=%s chunk_end=%s error_type=%s",
                run_id,
                current.isoformat(),
                chunk_end.isoformat(),
                type(error).__name__,
            )
            repository.record_chunk(run_id, current, chunk_end, None, "failed", error=str(error))
        current = chunk_end
    repository.finish_run(run_id, overall_status)
    logger.info("event=extraction_finished run_id=%s status=%s", run_id, overall_status)
    return run_id


def load(run_id: str, keys: list[str], store: S3RawStore, repository: PostgresRepository, secret: str) -> int:
    loaded = 0
    logger.info("event=load_started run_id=%s object_count=%s", run_id, len(keys))
    for key in keys:
        logger.info("event=object_load_started run_id=%s raw_key=%s", run_id, key)
        envelope = store.read_json(key)
        tweets = normalize_payload(envelope, secret)
        repository.upsert_tweets(tweets)
        loaded += len(tweets)
        logger.info(
            "event=object_load_succeeded run_id=%s raw_key=%s record_count=%s",
            run_id,
            key,
            len(tweets),
        )
    logger.info("event=load_finished run_id=%s record_count=%s", run_id, loaded)
    return loaded
