from pathlib import Path
from typing import Any

import psycopg

from .models import TweetRecord

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class PostgresRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def initialize(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(SCHEMA_PATH.read_text())

    def start_run(self, run_id: str, start: Any, end: Any) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "INSERT INTO pipeline_runs (run_id, requested_start, requested_end, status) VALUES (%s, %s, %s, 'running')",
                (run_id, start, end),
            )

    def finish_run(self, run_id: str, status: str, error: str | None = None) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "UPDATE pipeline_runs SET status=%s, finished_at=now(), error=%s WHERE run_id=%s",
                (status, error, run_id),
            )

    def record_chunk(self, run_id: str, start: Any, end: Any, key: str | None, status: str, count: int = 0, error: str | None = None) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "INSERT INTO pipeline_chunks (run_id, chunk_start, chunk_end, raw_key, status, record_count, error) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (run_id, start, end, key, status, count, error),
            )

    def upsert_tweets(self, tweets: list[TweetRecord]) -> None:
        if not tweets:
            return
        with psycopg.connect(self.database_url) as connection:
            connection.executemany(
                """INSERT INTO tweets (tweet_id, anonymized_user_id, location, follower_count, tweeted_at, hashtags, tweet_count, is_retweet)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (tweet_id) DO UPDATE SET anonymized_user_id=excluded.anonymized_user_id,
                location=excluded.location, follower_count=excluded.follower_count, tweeted_at=excluded.tweeted_at,
                hashtags=excluded.hashtags, tweet_count=excluded.tweet_count, is_retweet=excluded.is_retweet""",
                [(t.tweet_id, t.anonymized_user_id, t.location, t.follower_count, t.tweeted_at, t.hashtags, t.tweet_count, t.is_retweet) for t in tweets],
            )
