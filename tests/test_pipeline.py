from datetime import datetime, timezone

from twitter_app.pipeline import extract


class Source:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, start, end):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary source outage")
        return {"data": []}


class Store:
    def put_immutable(self, run_id, start, end, payload):
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
    run_id = extract(
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
        1,
        Source(),
        Store(),
        repository,
    )
    assert run_id == repository.run_id
    assert len(repository.chunks) == 2
    assert repository.finished == "failed"
