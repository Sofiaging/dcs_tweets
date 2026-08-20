install:
	python3 -m pip install -e '.[dev]'

check:
	ruff check .
	pytest

up:
	docker compose up -d postgres minio

down:
	docker compose down
