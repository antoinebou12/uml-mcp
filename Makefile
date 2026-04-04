.PHONY: help install install-dev clean test lint typecheck coverage ci docs docs-serve docker-build docker-run docker-test docker-stop

# Default target
help:
	@echo "UML-MCP Makefile"
	@echo "----------------"
	@echo "Commands:"
	@echo "  make install        Install production dependencies"
	@echo "  make install-dev    Install development dependencies"
	@echo "  make clean          Clean temporary files and caches"
	@echo "  make test           Run tests"
	@echo "  make lint           Run linting checks (ruff + pre-commit)"
	@echo "  make typecheck      Run type checker (ty)"
	@echo "  make coverage       Run tests with coverage report"
	@echo "  make ci             Run same steps as CI (lint + tests + coverage; use with 'act' or locally)"
	@echo "  make docs            Build documentation (MkDocs)"
	@echo "  make docs-serve      Build and serve documentation locally (MkDocs)"
	@echo "  make docker-build   Build Docker images"
	@echo "  make docker-run     Run services using Docker Compose"
	@echo "  make docker-test    Run tests in Docker container"
	@echo "  make docker-stop    Stop Docker containers"

# Installation targets
install:
	uv sync

install-dev: install
	uv sync --all-groups

# Cleaning
clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf .ty_cache
	find . -name "*.pyc" -delete

# Testing and linting
test:
	uv run pytest -xvs tests/

lint:
	uv run ruff check .
	uv run ruff format --check .
	pre-commit run --all-files

typecheck:
	uv run ty check

coverage:
	uv run pytest --cov=mcp_core --cov=tools --cov-report=term --cov-report=html

# Same steps as .github/workflows/ci.yml (test job) for local/act runs
ci: install-dev
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest --cov=mcp_core --cov=tools --cov-report=term --cov-report=html

# Documentation (MkDocs)
docs: install-dev
	uv run mkdocs build

docs-serve: install-dev
	uv run mkdocs serve

# Docker commands
docker-build:
	docker-compose build

docker-run:
	docker-compose up -d

docker-test:
	docker-compose run --rm uml-mcp pytest -xvs

docker-stop:
	docker-compose down
