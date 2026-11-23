# GoatCash

<p align="center">
  <img src="assets/goatcash-logo.png" alt="Logo GoatCash" width="280" />
</p>

[English version: README.md](README.md)

Otwarta platforma analityczna rynku kryptowalut: agenci analityczni, prognozy rozliczane
w Forecast Ledger, kalibracja i samouczenie z twardymi granicami, a w dalszych etapach
bot handlowy w trybach o rosnącej autonomii.

> **Status:** etap **E1** (repozytorium, standardy, CI, sekrety). Funkcje pojawiają się
> zgodnie z roadmapą E0–E18; każdy etap kończy się bramką jakości sprawdzaną automatycznie.

## Struktura

```
apps/web/              Next.js (frontend)
services/platform/     pakiet Python `goatcash` (api, worker, ingest, scheduler)
services/executor/     executor bota (osobny obraz, osobne sekrety)
packages/contracts/    OpenAPI, JSON Schema zdarzeń, klient TS (od E2)
ml/                    trening i notatniki (bez danych)
prompts/               prompty LLM z wersjami
infra/terraform/       Oracle, Cloudflare (od E3)
infra/ansible/         konfiguracja serwerów (od E3)
infra/compose/         Docker Compose dla dev, staging, prod (od E3)
infra/secrets/         pliki *.enc.yaml zaszyfrowane SOPS + age
docs/adr/              decyzje architektoniczne
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
make gate G=1    # testy automatyczne bramki G1, raport w reports/gates/
```

## Bezpieczeństwo

W repozytorium jest tylko to, co mogłoby trafić na pierwszą stronę gazety. Sekrety są
zaszyfrowane SOPS albo trzymane poza repo; pięć warstw ochrony opisuje `SECURITY.md`.
Podatności zgłaszaj prywatnie (patrz `SECURITY.md`).

## Licencja

[GNU AGPL-3.0](LICENSE): kto udostępnia zmodyfikowaną wersję jako usługę sieciową,
musi udostępnić jej kod źródłowy.
