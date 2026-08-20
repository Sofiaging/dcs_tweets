from collections.abc import Iterator
from datetime import datetime
from typing import Any, Protocol

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class TweetSource(Protocol):
    def search(self, start: datetime, end: datetime) -> dict[str, Any]: ...


class XApiSource:
    endpoint = "https://api.x.com/2/tweets/search/recent"

    def __init__(self, bearer_token: str, page_size: int = 100) -> None:
        self.page_size = page_size
        self.client = httpx.Client(
            headers={"Authorization": f"Bearer {bearer_token}"}, timeout=30
        )

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError,)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def search(self, start: datetime, end: datetime) -> dict[str, Any]:
        response = self.client.get(
            self.endpoint,
            params={
                "query": "#ChargeNow",
                "start_time": start.isoformat().replace("+00:00", "Z"),
                "end_time": end.isoformat().replace("+00:00", "Z"),
                "max_results": self.page_size,
                "tweet.fields": "created_at,entities,public_metrics,referenced_tweets,author_id",
                "user.fields": "location,public_metrics",
                "expansions": "author_id",
            },
        )
        response.raise_for_status()
        return response.json()
