.PHONY: install run test lint examples evaluate aggregate full-cycle docker-build docker-run

install:
	pip install -e ".[dev]"

run:
	uvicorn triage.api:app --reload --host 0.0.0.0 --port 8000

test:
	pytest

lint:
	ruff check .
	ruff format --check .

examples:
	python scripts/run_examples.py

evaluate:
	python -m evaluation.run_evaluation --all-pending

aggregate:
	python -m evaluation.run_evaluation --aggregate-only

full-cycle: examples evaluate

docker-build:
	docker build -t triage-backend .

docker-run:
	docker run --rm -p 8000:8000 --env-file ../.env triage-backend
