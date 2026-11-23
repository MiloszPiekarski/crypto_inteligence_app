# GoatCash: komendy deweloperskie (E1.8). `make help` pokazuje listę.
SHELL := /bin/bash
.DEFAULT_GOAL := help
G ?=

.PHONY: help install tools dev lint audit fmt typecheck imports test db-migration-test event-schemas-test evidence-test openapi-lint openapi build secrets-scan doctor gate

help: ## Lista komend
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Instaluje zależności Python i Node oraz hooki pre-commit
	uv sync --frozen
	pnpm install --frozen-lockfile
	uv run pre-commit install

dev: ## Uruchamia frontend w trybie developerskim (backend dochodzi w E3/E6)
	pnpm --filter @goatcash/web dev

lint: ## Lint i format (ruff, Biome)
	uv run ruff check .
	uv run ruff format --check .
	pnpm lint

tools: ## Narzędzia bramek w wersjach z CI (przypięte, sumy SHA-256) do .tools/bin
	./scripts/ci/install-tools.sh .tools

audit: ## Statyczna kontrola: shellcheck, hadolint, actionlint, zizmor
	./scripts/audit.sh

fmt: ## Automatyczne formatowanie
	uv run ruff check --fix .
	uv run ruff format .
	pnpm format

typecheck: ## Typy: pyright (strict) i tsc
	uv run pyright
	pnpm typecheck

imports: ## Granice modułów (import-linter)
	uv run lint-imports

test: ## Testy jednostkowe z pokryciem
	uv run pytest --cov --cov-report=term --cov-report=xml
	pnpm test

db-migration-test: ## Migracje w obie strony na czystym Postgresie z Timescale (Docker; bramka G2)
	uv run pytest -m migration services/platform/tests/migrations

event-schemas-test: ## JSON Schema zdarzeń: poprawne przykłady przechodzą, błędne odrzucone (G2)
	uv run pytest packages/contracts/tests/test_event_schemas.py

evidence-test: ## Kontrakt Evidence v1: poprawne przykłady przechodzą, błędne odrzucone (G2)
	uv run pytest packages/contracts/tests/test_evidence_schema.py

openapi-lint: ## OpenAPI zgodne z aplikacją, Spectral bez błędów i ostrzeżeń, klient TS aktualny (G2)
	uv run python scripts/export_openapi.py --check
	pnpm --filter @goatcash/contracts lint:openapi
	pnpm --filter @goatcash/contracts exec openapi-typescript openapi/openapi.json --output src/api.ts --check
	pnpm --filter @goatcash/contracts typecheck

openapi: ## Regeneruje specyfikację OpenAPI i klienta TS po zmianie API
	uv run python scripts/export_openapi.py
	pnpm --filter @goatcash/contracts generate

build: ## Build frontendu
	pnpm build

secrets-scan: ## gitleaks na całej historii repozytorium
	gitleaks git --config .gitleaks.toml --redact --verbose .

doctor: ## Gotowość komputera i dostęp do usług (bramka G0)
	./scripts/doctor.sh

gate: ## Bramka jakości z gates/G<nr>.yaml: make gate G=<nr>, raport w reports/gates/
	@test -n "$(G)" || (echo "Użycie: make gate G=<nr>, np. make gate G=1" && exit 2)
	uv run --frozen python scripts/gate.py $(G)
