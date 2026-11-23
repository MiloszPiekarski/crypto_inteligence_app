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
