from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TweetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tweet_id: str = Field(min_length=1)
    anonymized_user_id: str = Field(min_length=1)
    location: str | None = None
    follower_count: int | None = Field(default=None, ge=0)
    tweeted_at: datetime
    hashtags: list[str] = Field(default_factory=list)
    tweet_count: int | None = Field(default=None, ge=0)
    is_retweet: bool = False

# below is not being used anywhere, but we keep it for reference in case we want to use it in the future
class RawEnvelope(BaseModel):
    """Exact provider response plus extraction metadata."""

    model_config = ConfigDict(extra="allow")

    run_id: str
    chunk_start: datetime
    chunk_end: datetime
    extracted_at: datetime
    payload: dict[str, Any]
