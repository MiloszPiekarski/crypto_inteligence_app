# GoatCash

<p align="center">
  <img src="assets/goatcash-logo.png" alt="Logo GoatCash" width="280" />
</p>

[English version: README.md](README.md)

Otwarta platforma analityczna rynku kryptowalut: agenci analityczni, prognozy rozliczane
w Forecast Ledger, kalibracja i samouczenie z twardymi granicami, a w dalszych etapach
bot handlowy w trybach o rosnącej autonomii.

> **Status:** etapy **E0–E2** zakończone (bramki G0–G2 zaliczone: konta i narzędzia;
> repozytorium, CI i sekrety; architektura szczegółowa, model danych i kontrakty). Następny:
> **E3** (infrastruktura bazowa). Funkcje pojawiają się zgodnie z roadmapą E0–E18; każdy etap
> kończy się bramką jakości sprawdzaną automatycznie. Bieżący stan: `docs/stan-pracy.md`.

## Struktura

```
apps/web/              Next.js (frontend)
services/platform/     pakiet Python `goatcash` (api, worker, ingest, scheduler)
services/executor/     executor bota (osobny obraz, osobne sekrety)
packages/contracts/    OpenAPI, JSON Schema zdarzeń, kontrakt Evidence, klient TS
ml/                    trening i notatniki (bez danych)
prompts/               prompty LLM z wersjami
infra/terraform/       Oracle, Cloudflare (od E3)
infra/ansible/         konfiguracja serwerów (od E3)
infra/compose/         Docker Compose dla dev, staging, prod (od E3)
infra/secrets/         pliki *.enc.yaml zaszyfrowane SOPS + age
docs/adr/              decyzje architektoniczne (ADR-0001…0006)
docs/architektura/     model zagrożeń (STRIDE) i diagramy C4
docs/wymagania.yaml    wymagania funkcjonalne i niefunkcjonalne
docs/gates/            raporty bramek jakości
tests/e2e/             Playwright (od E12)
.github/workflows/     CI/CD
```

## Start (macOS)

Wymagane narzędzia sprawdza `make doctor` (bramka G0). Potem:

```bash
make install     # uv sync + pnpm install + hooki pre-commit
make lint        # ruff + Biome
make typecheck   # pyright (strict) + tsc
make imports     # granice modułów (import-linter)
make test        # pytest z pokryciem + vitest
make gate G=1    # testy automatyczne bramki (G=1, G=2, ...), raport w reports/gates/
```

Kontrakty i baza (bramka G2; migracje wymagają włączonego Docker Desktop):

```bash
make db-migration-test   # Alembic upgrade/downgrade na Postgresie 17 + TimescaleDB
make event-schemas-test  # JSON Schema zdarzeń: poprawne przykłady przechodzą, błędne nie
make evidence-test       # kontrakt Evidence v1
make openapi-lint        # OpenAPI zgodne z aplikacją, Spectral, klient TS aktualny
make openapi             # regeneracja OpenAPI i klienta TS po zmianie API
make requirements-check  # każde wymaganie ma ID, etap, bramkę i mierzalny próg
```

## Bezpieczeństwo

W repozytorium jest tylko to, co mogłoby trafić na pierwszą stronę gazety. Sekrety są
zaszyfrowane SOPS albo trzymane poza repo; pięć warstw ochrony opisuje `SECURITY.md`.
Podatności zgłaszaj prywatnie (patrz `SECURITY.md`).

## Licencja

[GNU AGPL-3.0](LICENSE): kto udostępnia zmodyfikowaną wersję jako usługę sieciową,
musi udostępnić jej kod źródłowy.
