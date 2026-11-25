.PHONY: install dev test lint up down logs shell migrate run bootstrap

bootstrap:
	python scripts/bootstrap_local.py

install:
	pip install -e ".[dev]"

dev:
	pip install -e ".[dev]"

test:
	python -m pytest -q

lint:
	ruff check src tests
	ruff format --check src tests
	mypy src

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f app

shell:
	docker compose exec app bash

migrate:
	alembic upgrade head

run:
	python -m bot.main

test-env:
	python scripts/check_env.py

test-extract:
	python scripts/test_extract.py "$(URL)"

test-probe:
	python scripts/probe_apify_actor.py "$(URL)" --actor $(ACTOR)

resolve-owner:
	python -m cli resolve-owner "$(INPUT)"

up-sqlite:
	docker compose -f docker-compose.sqlite.yml up -d --build