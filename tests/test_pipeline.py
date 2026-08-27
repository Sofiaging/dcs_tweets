import logging
from datetime import datetime, timezone

import pytest

from twitter_app.pipeline import extract, extract_intervals, load


class Source:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, start, end):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary source outage")
        return {"data": []}


class Store:
    def __init__(self):
        self.payloads = []

    def put_immutable(self, run_id, start, end, payload):
        self.payloads.append(payload)
        return f"{run_id}/{start.isoformat()}"


class Repository:
    def __init__(self):
        self.chunks = []
        self.finished = None

    def start_run(self, run_id, start, end):
        self.run_id = run_id

    def record_chunk(self, *args, **kwargs):
        self.chunks.append((args, kwargs))

    def finish_run(self, run_id, status, error=None):
        self.finished = status


def test_failed_chunk_does_not_prevent_later_chunks() -> None:
    repository = Repository()
    store = Store()
    run_id = extract(
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
        1,
        Source(),
        store,
        repository,
    )
    assert run_id == repository.run_id
    assert len(repository.chunks) == 2
    assert repository.finished == "failed"


class EmptySource:
    def search(self, start, end):
        return {
            "data": [],
            "includes": {"users": []},
            "meta": {"result_count": 0, "page_count": 1},
        }


def test_empty_extraction_is_stored_as_a_successful_chunk(caplog) -> None:
    caplog.set_level(logging.INFO)
    repository = Repository()
    store = Store()

    run_id = extract(
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
        1,
        EmptySource(),
        store,
        repository,
    )

    assert store.payloads == [{
        "data": [],
        "includes": {"users": []},
        "meta": {"result_count": 0, "page_count": 1},
    }]
    assert repository.chunks == [(
        (
            run_id,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            f"{run_id}/2026-01-01T00:00:00+00:00",
            "succeeded",
            0,
            None,
        ),
        {},
    )]
    assert repository.finished == "succeeded"
    assert "event=extraction_started" in caplog.text
    assert "event=chunk_succeeded" in caplog.text
    assert "record_count=0" in caplog.text
    assert "event=extraction_finished" in caplog.text


class EmptyRawStore:
    def read_json(self, key):
        return {
            "data": [],
            "includes": {"users": []},
            "meta": {"result_count": 0, "page_count": 1},
        }


class LoadRepository:
    def __init__(self):
        self.upserted = []

    def upsert_tweets(self, tweets):
        self.upserted.extend(tweets)


def test_loading_empty_raw_data_is_a_successful_no_op(caplog) -> None:
    caplog.set_level(logging.INFO)
    repository = LoadRepository()

    loaded = load("run-id", ["empty.json"], EmptyRawStore(), repository, "secret")

    assert loaded == 0
    assert repository.upserted == []
    assert "event=load_started" in caplog.text
    assert "event=object_load_succeeded" in caplog.text
    assert "record_count=0" in caplog.text
    assert "event=load_finished" in caplog.text


def test_selected_failed_intervals_can_be_reprocessed_without_successful_ones() -> None:
    repository = Repository()
    store = Store()
    failed_interval = (
        datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
    )

    extract_intervals(
        failed_interval[0],
        failed_interval[1],
        [failed_interval],
        EmptySource(),
        store,
        repository,
    )

    assert len(repository.chunks) == 1
    assert repository.chunks[0][0][1:3] == failed_interval
    assert repository.finished == "succeeded"


class InterruptingSource:
    def search(self, start, end):
        raise KeyboardInterrupt


def test_interrupted_run_is_finalized_as_failed() -> None:
    repository = Repository()

    with pytest.raises(KeyboardInterrupt):
        extract(
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            1,
            InterruptingSource(),
            Store(),
            repository,
        )

    assert repository.finished == "failed"


@pytest.mark.parametrize(
    ("chunk_hours", "extraction_workers", "message"),
    [(0, 1, "chunk_hours"), (1, 0, "extraction_workers")],
)
def test_invalid_scaling_configuration_is_rejected(
    chunk_hours, extraction_workers, message
) -> None:
    with pytest.raises(ValueError, match=message):
        extract(
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            chunk_hours,
            EmptySource(),
            Store(),
            Repository(),
            extraction_workers,
        )
