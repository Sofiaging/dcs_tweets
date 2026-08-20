import hashlib
import hmac
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from .models import TweetRecord


def anonymize_user_id(user_id: str, secret: str) -> str:
    return hmac.new(secret.encode(), user_id.encode(), hashlib.sha256).hexdigest()


def normalize_payload(payload: dict[str, Any], secret: str) -> list[TweetRecord]:
    users = {user["id"]: user for user in payload.get("includes", {}).get("users", [])}
    records: list[TweetRecord] = []
    for tweet in payload.get("data", []):
        author_id = tweet.get("author_id")
        created_at = tweet.get("created_at")
        if not author_id or not created_at or not tweet.get("id"):
            continue
        user = users.get(author_id, {})
        metrics = user.get("public_metrics", {})
        tweet_metrics = tweet.get("public_metrics", {})
        entities = tweet.get("entities", {})
        hashtags = [item["tag"] for item in entities.get("hashtags", []) if item.get("tag")]
        references = tweet.get("referenced_tweets", [])
        records.append(
            TweetRecord(
                tweet_id=str(tweet["id"]),
                anonymized_user_id=anonymize_user_id(str(author_id), secret),
                location=user.get("location"),
                follower_count=metrics.get("followers_count"),
                tweeted_at=datetime.fromisoformat(created_at.replace("Z", "+00:00")),
                hashtags=hashtags,
                tweet_count=tweet_metrics.get("impression_count"),
                is_retweet=any(ref.get("type") == "retweeted" for ref in references),
            )
        )
    return records
