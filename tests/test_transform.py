from twitter_app.transform import anonymize_user_id, normalize_payload


def test_anonymization_is_deterministic_and_secret_scoped() -> None:
    assert anonymize_user_id("42", "secret") == anonymize_user_id("42", "secret")
    assert anonymize_user_id("42", "secret") != anonymize_user_id("42", "other")


def test_normalize_payload_extracts_required_fields() -> None:
    payload = {
        "data": [{
            "id": "tweet-1",
            "author_id": "user-1",
            "created_at": "2026-01-01T12:00:00Z",
            "entities": {"hashtags": [{"tag": "ChargeNow"}]},
            "referenced_tweets": [{"type": "retweeted", "id": "old"}],
        }],
        "includes": {"users": [{
            "id": "user-1",
            "location": "Sofia",
            "public_metrics": {"followers_count": 12, "tweet_count": 7},
        }]},
    }
    record = normalize_payload(payload, "secret")[0]
    assert record.tweet_id == "tweet-1"
    assert record.location == "Sofia"
    assert record.follower_count == 12
    assert record.hashtags == ["ChargeNow"]
    assert record.tweet_count == 7
    assert record.is_retweet is True


def test_empty_payload_is_valid() -> None:
    assert normalize_payload({}, "secret") == []


def test_normalization_ignores_unknown_fields_and_defaults_optional_fields() -> None:
    payload = {
        "data": [{
            "id": "tweet-2",
            "author_id": "user-2",
            "created_at": "2026-01-01T12:00:00Z",
            "a_new_tweet_field": "ignored",
        }],
        "includes": {"users": [{
            "id": "user-2",
            "a_new_user_field": "ignored",
        }]},
        "a_new_top_level_field": "ignored",
    }

    record = normalize_payload(payload, "secret")[0]

    assert record.tweet_id == "tweet-2"
    assert record.location is None
    assert record.follower_count is None
    assert record.hashtags == []
    assert record.tweet_count is None
    assert record.is_retweet is False
