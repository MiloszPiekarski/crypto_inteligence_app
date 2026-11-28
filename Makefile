# GoatCash: komendy deweloperskie (E1.8). `make help` pokazuje listę.
SHELL := /bin/bash
.DEFAULT_GOAL := help
G ?=

.PHONY: ansible-test help install tools dev lint audit fmt typecheck imports test db-migration-test image-migration-test iac-lint compose-staging-test backup-restore-test marketdata-normalization-test marketdata-dq-test marketdata-resilience-test marketdata-logic-test marketdata-db-test features-reference-test features-pit-test features-gaps-test features-determinism-test features-db-test api-schema-test api-security-test api-data-test api-db-test api-migration-test event-schemas-test evidence-test openapi-lint openapi requirements-check build secrets-scan doctor gate

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

iac-lint: ## Terraform (fmt, validate, tflint), trivy config, ansible-lint; autotest na wzorcach (G3)
	./scripts/iac-lint.sh

compose-staging-test: ## Compose staging: wdrożenie, test dymny, kopia, rollback na zepsutym obrazie (Docker; G3)
	./scripts/compose_staging_test.sh

backup-restore-test: ## pgBackRest: pełna+przyrostowa+WAL, odtworzenie i PITR, sumy wszystkich tabel (Docker; G3, F-02)
	./scripts/backup_restore_test.sh

ansible-test: ## Ansible site.yml na kontenerze Ubuntu 24.04 z systemd: 2 przebiegi, stan serwera (Docker; G3)
	./scripts/ansible_test.sh

image-migration-test: ## Obraz platformy uruchamia migracje na Postgresie z Timescale (Docker; bramka G3)
	uv run pytest -m image services/platform/tests/image

marketdata-normalization-test: ## Normalizacja na nagranych odpowiedziach OKX i Bybit, kasety obu giełd (G4p)
	uv run pytest --no-cov -m "fixtures_complete or not (db or migration or image)" services/platform/tests/marketdata/test_normalization.py

marketdata-dq-test: ## DQ: 200 wstrzykniętych błędów, fałszywe alarmy, reguły z wartościami referencyjnymi (G4p)
	uv run pytest --no-cov -s services/platform/tests/marketdata/test_dq_injection.py services/platform/tests/marketdata/test_dq_rules.py

marketdata-resilience-test: ## 429, błąd sieci, przerwanie i wznowienie uzupełniania historii (G4p)
	uv run pytest --no-cov services/platform/tests/marketdata/test_resilience.py

marketdata-logic-test: ## Luki, kompletność, cena referencyjna, candle.closed, raport danych (G4p)
	uv run pytest --no-cov services/platform/tests/marketdata/test_gaps_refprice_events.py services/platform/tests/marketdata/test_ingest.py

marketdata-db-test: ## marketdata na Postgresie z Timescale i Valkey w kontenerach (Docker; G4p)
	uv run pytest --no-cov -m db services/platform/tests/marketdata/test_pgstore.py

features-reference-test: ## Cechy fs-1p vs TA-Lib, czysty Python i przykłady ręczne, dane syntetyczne i prawdziwe (G5p)
	uv run pytest --no-cov services/platform/tests/features/test_reference.py

features-pit-test: ## Brak zaglądania w przyszłość: 1000 losowych chwil, replay known_at, mutacje (G5p, F-07)
	uv run pytest --no-cov services/platform/tests/features/test_point_in_time.py services/platform/tests/features/test_view.py

features-gaps-test: ## Braki danych: NaN + status, bez interpolacji, DQ E4, mutacja wypełniania luk (G5p)
	uv run pytest --no-cov services/platform/tests/features/test_gaps.py

features-determinism-test: ## Dwa pełne przeliczenia historii bit w bit, wersja zbioru cech (G5p, F-08)
	uv run pytest --no-cov services/platform/tests/features/test_determinism.py

features-db-test: ## Cechy w Postgresie z Timescale i Valkey: zapis bit w bit, outbox, konsument (Docker; G5p)
	uv run pytest --no-cov -m db services/platform/tests/features/test_feature_db.py

api-schema-test: ## Schemathesis: API v1 zgodne z OpenAPI, 0 odpowiedzi niezgodnych, 0 błędów 5xx (G6p, F-09)
	uv run pytest --no-cov services/platform/tests/api/test_api_schemathesis.py

api-security-test: ## Nagłówki bezpieczeństwa na każdej odpowiedzi i CORS tylko dla app.goatcash.app (G6p)
	uv run pytest --no-cov services/platform/tests/api/test_api_security.py

api-data-test: ## Endpointy rynkowe: świece = candles_ref, 4h/1d vs niezależne przeliczenie, paginacja, błędy (G6p)
	uv run pytest --no-cov services/platform/tests/api/test_api_market.py services/platform/tests/test_http_api.py

api-db-test: ## API na Postgresie z Timescale: baza = pamięć, konto tylko do odczytu, Schemathesis (Docker; G6p)
	uv run pytest --no-cov -m db services/platform/tests/api/test_api_db.py

api-migration-test: ## Migracja 0005 w górę i w dół z danymi, bez utraty danych (Docker; G6p)
	uv run pytest --no-cov -m migration services/platform/tests/migrations/test_migration_0005.py

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

requirements-check: ## Wymagania F-xx i NF-xx kompletne: ID, etap, bramka, mierzalny próg (G2)
	uv run python scripts/check_requirements.py

build: ## Build frontendu
	pnpm build

secrets-scan: ## gitleaks na całej historii repozytorium
	gitleaks git --config .gitleaks.toml --redact --verbose .

doctor: ## Gotowość komputera i dostęp do usług (bramka G0)
	./scripts/doctor.sh

gate: ## Bramka jakości z gates/G<nr>.yaml: make gate G=<nr>, raport w reports/gates/
	@test -n "$(G)" || (echo "Użycie: make gate G=<nr>, np. make gate G=1" && exit 2)
	uv run --frozen python scripts/gate.py $(G)
