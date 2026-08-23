from datetime import datetime
from typing import Any, Protocol

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class TweetSource(Protocol):
    def search(self, start: datetime, end: datetime) -> dict[str, Any]: ...


class SourceResponseError(ValueError):
    """The source returned a response with an incompatible structure."""


def response_items(container: dict[str, Any], key: str, path: str) -> list[dict[str, Any]]:
    """Return an optional list of objects, rejecting incompatible API changes."""
    value = container.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise SourceResponseError(f"Expected {path} to be a list of objects")
    return value


class MockTweetSource:
    """Generate deterministic X-shaped data without making network requests."""

    def search(self, start: datetime, end: datetime) -> dict[str, Any]:
        interval_id = int(start.timestamp())
        author_id = f"mock-user-{interval_id % 3 + 1}"
        tweeted_at = start + (end - start) / 2
        is_retweet = interval_id % 2 == 0
        tweet = {
            "id": f"mock-tweet-{interval_id}",
            "author_id": author_id,
            "created_at": tweeted_at.isoformat().replace("+00:00", "Z"),
            "entities": {"hashtags": [{"tag": "ChargeNow"}]},
            "referenced_tweets": (
                [{"type": "retweeted", "id": f"mock-original-{interval_id}"}]
                if is_retweet
                else []
            ),
        }
        user = {
            "id": author_id,
            "location": "Sofia",
            "public_metrics": {
                "followers_count": 100 + interval_id % 50,
                "tweet_count": 1_000 + interval_id % 500,
            },
        }
        return {
            "data": [tweet],
            "includes": {"users": [user]},
            "meta": {"result_count": 1, "page_count": 1, "mock": True},
        }


class XApiSource:
    recent_endpoint = "https://api.x.com/2/tweets/search/recent"
    archive_endpoint = "https://api.x.com/2/tweets/search/all"

    def __init__(
        self,
        bearer_token: str,
        page_size: int = 100,
        use_full_archive: bool = False,
    ) -> None:
        self.page_size = page_size
        self.endpoint = self.archive_endpoint if use_full_archive else self.recent_endpoint
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
        params: dict[str, Any] = {
            "query": "#ChargeNow",
            "start_time": start.isoformat().replace("+00:00", "Z"),
            "end_time": end.isoformat().replace("+00:00", "Z"),
            "max_results": self.page_size,
            "tweet.fields": "created_at,entities,referenced_tweets,author_id",
            "user.fields": "location,public_metrics",
            "expansions": "author_id",
        }
        tweets: list[dict[str, Any]] = []
        users_by_id: dict[str, dict[str, Any]] = {}
        page_count = 0

        while True:
            response = self.client.get(self.endpoint, params=params)
            response.raise_for_status()
            page = response.json()
            if not isinstance(page, dict):
                raise SourceResponseError("Expected the X API response to be a JSON object")
            page_count += 1

            tweets.extend(response_items(page, "data", "data"))

            includes = page.get("includes", {})
            if not isinstance(includes, dict):
                raise SourceResponseError("Expected includes to be a JSON object")
            for user in response_items(includes, "users", "includes.users"):
                if user_id := user.get("id"):
                    users_by_id[user_id] = user

            meta = page.get("meta", {})
            if not isinstance(meta, dict):
                raise SourceResponseError("Expected meta to be a JSON object")
            next_token = meta.get("next_token")
            if next_token is not None and not isinstance(next_token, str):
                raise SourceResponseError("Expected meta.next_token to be a string")
            if not next_token:
                break
            params["pagination_token"] = next_token

        return {
            "data": tweets,
            "includes": {"users": list(users_by_id.values())},
            "meta": {"result_count": len(tweets), "page_count": page_count},
        }
