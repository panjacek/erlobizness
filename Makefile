DOCKER_RUN_ARGS := --rm --user $(shell id -u):$(shell id -g) -v $(CURDIR):/app -w /app node:24-slim
DOCKER_PW_ARGS := --rm --network host --user $(shell id -u):$(shell id -g) -e HOME=/tmp -e E2E_IN_DOCKER=1 -v $(CURDIR):/app -w /app mcr.microsoft.com/playwright:v1.62.1-noble

.PHONY: help up test test-py coverage test-js test-e2e lint lint-py lint-js format format-py format-js

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Run dev server with auto-reload (http://localhost:8000)
	ERLO_ALLOW_INJECTION=1 PYTHONPATH=src uv run uvicorn erlobiznes.web_app:app --reload --reload-include "*.js" --reload-include "*.css" --reload-include "*.html" --host 0.0.0.0 --port 8000

test: test-py test-js ## Run all suites (pytest + vitest)
	@echo "All tests done"

test-py: ## Run python suite
	uv run pytest

coverage: ## Pytest with coverage report (term + xml)
	uv run pytest --cov --cov-report=term-missing --cov-report=xml

test-js: ## Run js suite (vitest via Docker)
	docker run $(DOCKER_RUN_ARGS) sh -c "npm install && npx vitest run"

test-e2e: ## Run browser E2E via Playwright Docker image (requires `make up` running; Linux only - uses host networking)
	docker run $(DOCKER_PW_ARGS) npx playwright test

lint: lint-py lint-js ## Run all linters (ruff + biome)
	@echo "Linting done"

lint-py: ## Ruff check
	uv run ruff check .

lint-js: ## Biome lint via Docker
	docker run $(DOCKER_RUN_ARGS) sh -c "npx @biomejs/biome lint ."

format: format-py format-js ## Auto-format both stacks
	@echo "Formatting done"

format-py: ## Ruff autofix + format
	uv run ruff check --fix .
	uv run ruff format .

format-js: ## Biome write via Docker
	docker run $(DOCKER_RUN_ARGS) sh -c "npx @biomejs/biome check --write ."
