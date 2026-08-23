install:
	python3 -m pip install -e '.[dev]'

check:
	ruff check .
	pytest

init-db:
	twitter-pipeline init-db
