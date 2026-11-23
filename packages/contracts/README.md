# packages/contracts

Kontrakty: OpenAPI, JSON Schema zdarzeń, wygenerowany klient TS (etap E2).

## Zdarzenia (`events/`, ADR-0003)

- `envelope.schema.json`: koperta każdego zdarzenia (`event_id` UUIDv7, `type`,
  `schema_version`, `occurred_at`, `producer` w postaci `proces@wersja`, `correlation_id`,
  `payload`).
- `<typ>.v1.schema.json`: pełne zdarzenie danego typu w wersji 1 (koperta + `payload`).
  Kwoty i ceny są tekstem dziesiętnym (bez utraty dokładności, ADR-0002).
- `examples/<typ>/valid/*.json` i `examples/<typ>/invalid/*.json`: przykłady; w błędnych
  pole `_why` opisuje naruszoną regułę (test usuwa je przed walidacją).
- Test: `make event-schemas-test` (bramka G2). Zmiana niezgodna wstecz = nowy plik
  `<typ>.v2.schema.json`; konsument obsługuje bieżącą i poprzednią wersję.

## `Evidence` v1 (`evidence/`)

- `evidence.v1.schema.json`: dowód agenta z polami z roadmapy E2 (agent i wersje, aktyw,
  `as_of`, `data_cutoff`, horyzont, `p_up`, kwantyle, `regime_view`, `facts`,
  `invalidation`, `status`). Dowód musi coś prognozować: `p_up` albo kwantyle.
- Reguły, których JSON Schema nie wyraża (`data_cutoff <= as_of`, kwantyle niemalejące),
  egzekwuje walidator Pydantic w E7 (tabela testów E7: blokada publikacji dowodu); w bazie
  `data_cutoff <= as_of` pilnuje już CHECK z migracji 0001.
- Test: `make evidence-test` (bramka G2). Kolumna `evidence.regime_view` (migracja 0002).

## API (`openapi/`, `src/`)

- `openapi/openapi.json`: specyfikacja OpenAPI 3.1 generowana z aplikacji FastAPI
  (`goatcash.http_api`); w E2 szkic: endpointy z roadmapy E6, E7 i E9 zwracają 501
  (RFC 9457), działa tylko `/v1/health`.
- `src/api.ts`: typy generowane przez openapi-typescript; `src/index.ts`: klient
  (`createApiClient`, openapi-fetch). Pliki generowane nie są formatowane przez Biome.
- Po zmianie API: `make openapi` (regeneracja), potem commit obu plików.
- Kontrola: `make openapi-lint` (bramka G2): specyfikacja zgodna z aplikacją, Spectral
  (`openapi/.spectral.yaml`) bez błędów i ostrzeżeń, typy TS aktualne, `tsc` bez błędów.
