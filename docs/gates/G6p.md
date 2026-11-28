# Bramka pracy G6p (E6, ścieżka pracy inżynierskiej): raport

- **Status:** w toku (szkic z PR 1 E6). Bramka jest w jobie `gate-next` (poza `ci-ok`);
  sprawdzenie `cache` jest czerwone do PR 2 E6. Dowód i statusy powstają przy zamknięciu
  etapu (PR 3 E6).
- **Kryteria (`testy.md`, sekcja 3a, wiersz G6p; ADR-0008):** Schemathesis: 0 odpowiedzi
  niezgodnych ze schematem i 0 błędów 500; nagłówki bezpieczeństwa i CORS sprawdzone
  testem; migracje w górę i w dół z danymi bez utraty danych. Wymaganie F-09
  (`work_target` w `docs/wymagania.yaml`).
- **Definicja automatu:** [`gates/G6p.yaml`](../../gates/G6p.yaml), uruchomienie
  `make gate G=6p`. Dowód typu `ci` (G6p nie ma części na staging).

## Doprecyzowanie kryterium migracji (decyzja właściciela 28.11.2026)

Jawne doprecyzowanie kryterium „migracje w górę i w dół z danymi bez utraty danych”, bo
nie każda migracja da się cofnąć z danymi:

| Migracja | Test                                                  | Z danymi         | Co sprawdza                                                                                                                                                                                                                                                |
| -------- | ----------------------------------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0005     | `test_migration_0005.py` (G6p `migrations`, także G2) | tak              | 0004 → 0005 → 0004 → 0005 z danymi w 10 tabelach (aktywa, instrumenty, świece, `candles_ref`, DQ, punkty kontrolne, cechy, outbox): liczba wierszy i suma kontrolna treści **każdej** tabeli `public` (bez kolumny `public_id`) identyczne na każdym kroku |
| 0004     | `test_migration_0004.py` (G2)                         | odmowa           | z danymi w `feature_values` migracja 0004 w dół (i w górę) **przerywa się** zamiast po cichu zgubić cechy (E5); to jest zamierzone zachowanie, nie część „w dół z danymi”                                                                                  |
| 0001     | `test_migration_0001.py` (G2)                         | nie (pusta baza) | `upgrade head` → `downgrade base` → `upgrade head` na czystej bazie; pełny schemat, role i uprawnienia                                                                                                                                                     |

**„Bez utraty danych” przy `downgrade` 0005:** w dół znika tylko kolumna `assets.public_id`.
To kolumna generowana z symbolu (`md5('goatcash:asset:' || symbol)::uuid`, decyzja D2), więc
nie niesie żadnej informacji, której nie ma w `symbol`: ponowne 0005 odtwarza dokładnie te
same identyfikatory (test porównuje je przed i po), a wszystkie pozostałe dane są bit w bit
takie same. Publiczne identyfikatory API są więc stabilne także po cofnięciu migracji.

## Decyzje właściciela (28.11.2026)

1. **D1:** świece pod `/v1/assets/{asset_id}/candles` (kontrakt z E2), nie `/v1/candles`
   z karty E6 (do zapisania w roadmapie przy zamknięciu etapu).
2. **D2:** `assets.public_id` (UUID) z migracji 0005; `asset_id` nie wychodzi na zewnątrz.
3. **D3:** interwały `1h`, `4h`, `1d`; 4h i 1d to pełne okresy UTC ze świec 1h, okres
   z brakującą świecą 1h nie jest zwracany (test `test_period_with_missing_hour_is_not_returned`);
   `1m`, `5m`, `15m` usunięte z kontraktu do ścieżki produktu (zapytanie o nie: 422).
4. **D4:** `/v1/market/overview`: ostatnie zamknięcie, zmiana i wolumen 24 h (null, gdy
   brakuje świecy), najgorszy status DQ giełd pary.
5. **D5:** jedno kwotowanie z uniwersum (USDT), bez parametru w API.
6. **Konto bazy procesu api:** api wystawione do internetu nie łączy się kontem `postgres`
   z `SET ROLE` (`RESET ROLE` przywraca superużytkownika), tylko osobnym kontem logowania
   `goatcash_api` (członek wyłącznie `goatcash_readonly`, sesja tylko do odczytu, limit
   20 połączeń, `statement_timeout` 5 s), zakładanym przez `ensure-api-role.sh` przy każdym
   wdrożeniu. Hasło nie jest w SOPS: właściciel nie ma dostępu do konsoli (28.11.2026), więc
   `deploy.sh` tworzy je na serwerze przy pierwszym wdrożeniu (`env/api-read.env`, tryb 600)
   i ustawia kontu przy każdym wdrożeniu; nowy serwer = nowe hasło bez ręcznych kroków.
   Sekcja `api-read` w SOPS, jeśli kiedyś powstanie, ma pierwszeństwo. Zmiana sekretów:
   niezależny recenzent (zgoda właściciela 28.11.2026) przed scaleniem PR 1 (`CLAUDE.md`,
   tryb pkt 5).
7. **PR 2 (cache):** unieważnianie przez `XREAD` (każda instancja api dostaje każde
   zdarzenie `candle.closed`); niedostępny Valkey nie może dawać nieaktualnych danych.

## Doprecyzowania techniczne (do przeglądu przy zamknięciu)

- **Kursor nieprzezroczysty a Schemathesis:** kursor to tylko `next_cursor` wydany przez
  serwer (opis parametru w specyfikacji); inny tekst daje 400 w RFC 9457. Schemathesis
  uznaje taki tekst za „poprawne dane” (typ `string`), więc dla odpowiedzi 400 z błędem
  kursora wyłączone jest tylko sprawdzenie „poprawne dane przyjęte” (`positive_data_acceptance`);
  pozostałe sprawdzenia działają, a test wymaga, by treść błędu była błędem kursora.
- **Endpointy E7 i E9** (dowody, ocena, agenci) celowo zwracają 501 do swoich etapów, więc są
  poza Schemathesis (każdy 5xx byłby błędem); 501 w RFC 9457 sprawdza `test_http_api.py`.
- **Identyfikator w fazie generowania:** losowy UUID prawie zawsze daje 404, więc połowa
  przypadków Schemathesis dostaje identyfikator istniejącego aktywa (hak
  `before_generate_path_parameters`); bez tego wstrzyknięty błąd 500 w endpointcie świec
  nie był wykrywany (sprawdzone mutacją).
- **Dokumentacja HTML API** (Swagger UI, ReDoc) wyłączona: CSP `default-src 'none'`;
  specyfikacja pod `/openapi.json` i w `packages/contracts/openapi/openapi.json`.

## Podział E6 na PR-y (zaakceptowany przez właściciela 28.11.2026)

| PR  | Gałąź                    | Zakres                                                                                                                                                                                            | Stan |
| --- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---- |
| 1   | `claude/E6-api-odczyt`   | `gates/G6p.yaml`, `gate-next`, migracja 0005, czytnik rynku (pamięć, Postgres), 4 endpointy, RFC 9457, kursor, nagłówki, CORS, OpenAPI i klient TS, Schemathesis, konto `goatcash_api` na staging | ⏳   |
| 2   | `claude/E6-cache-valkey` | cache Valkey z TTL i unieważnianiem po `candle.closed` (XREAD), brak Valkey bez nieaktualnych danych                                                                                              | ⬜   |
| 3   | `claude/E6-g6p`          | G6p do macierzy `gate`, ten raport z dowodami, dokumentacja etapu                                                                                                                                 | ⬜   |
