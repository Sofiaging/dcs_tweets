from datetime import UTC, datetime

import pytest

from twitter_app.source import MockTweetSource, SourceResponseError, XApiSource


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Client:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []

    def get(self, endpoint, params):
        self.calls.append((endpoint, params.copy()))
        return Response(next(self.pages))


def test_endpoint_is_selected_by_archive_flag() -> None:
    recent = XApiSource("token")
    archive = XApiSource("token", use_full_archive=True)

    assert recent.endpoint.endswith("/tweets/search/recent")
    assert archive.endpoint.endswith("/tweets/search/all")


def test_mock_source_returns_deterministic_x_shaped_data() -> None:
    source = MockTweetSource()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 1, 1, tzinfo=UTC)

    first = source.search(start, end)
    second = source.search(start, end)

    assert first == second
    assert first["meta"]["mock"] is True
    assert first["data"][0]["author_id"] == first["includes"]["users"][0]["id"]
    assert first["includes"]["users"][0]["public_metrics"]["tweet_count"] >= 1_000


def test_search_follows_next_token_and_combines_pages() -> None:
    source = XApiSource("token")
    source.client = Client([
        {
            "data": [{"id": "tweet-1"}],
            "includes": {"users": [{"id": "user-1"}]},
            "meta": {"next_token": "page-2"},
        },
        {
            "data": [{"id": "tweet-2"}],
            "includes": {"users": [{"id": "user-1"}, {"id": "user-2"}]},
            "meta": {},
        },
    ])

    payload = source.search(
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert [tweet["id"] for tweet in payload["data"]] == ["tweet-1", "tweet-2"]
    assert [user["id"] for user in payload["includes"]["users"]] == ["user-1", "user-2"]
    assert payload["meta"] == {"result_count": 2, "page_count": 2}
    assert "pagination_token" not in source.client.calls[0][1]
    assert source.client.calls[1][1]["pagination_token"] == "page-2"


def test_search_tolerates_new_fields_and_missing_optional_collections() -> None:
    source = XApiSource("token")
    source.client = Client([{
        "meta": {"result_count": 0},
        "a_new_top_level_field": {"can": "be ignored"},
    }])

    payload = source.search(
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert payload == {
        "data": [],
        "includes": {"users": []},
        "meta": {"result_count": 0, "page_count": 1},
    }


@pytest.mark.parametrize(
    ("page", "message"),
    [
        ({"data": {}}, "data"),
        ({"includes": []}, "includes"),
        ({"includes": {"users": {}}}, "includes.users"),
        ({"meta": []}, "meta"),
        ({"meta": {"next_token": 123}}, "meta.next_token"),
    ],
)
def test_search_reports_incompatible_response_changes(page, message) -> None:
    source = XApiSource("token")
    source.client = Client([page])

    with pytest.raises(SourceResponseError, match=message):
        source.search(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        )
