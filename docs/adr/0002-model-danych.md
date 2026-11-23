# ADR-0002: Model danych

- **Status:** zatwierdzona 2026-11-22 (scalenie PR #24, commit `2e4cb62`)
- **Data:** 2026-11-22
- **Etap:** E2
- **Źródło:** roadmapa E2 („Model danych (grupy tabel)”), Fundamenty sekcje 1–2, ADR-0001

## Kontekst

Model danych musi wytrzymać wszystkie późniejsze etapy (dane rynkowe, cechy point-in-time,
agenci, rozliczanie prognoz, użytkownicy, alerty, backtesty, bot), bo zmiana fundamentów po E4
oznaczałaby migracje na żywych danych. Ograniczenia: jedna maszyna Oracle A1 (12 GB RAM,
wolumen 150 GB) w fazie budowy, jedna osoba, analizy liczone poprawnie co do wartości, executor
bota odizolowany od reszty (ADR-0006).

## Decyzja

1. **Jeden silnik:** PostgreSQL 17 + TimescaleDB + pgvector (ADR-0001). Wersje obrazu bazy są
   przypięte (digest) w `infra/` i w teście migracji.
2. **Schematy:** tabele platformy w `public`; tabele bota w osobnym schemacie `bot`; tabele
   Better Auth w `public` pod nazwami z roadmapy (ADR-0004).
3. **Jedno źródło schematu: Alembic.** Każda zmiana schematu to migracja pisana ręcznie
   (autogenerate tylko jako podpowiedź), z działającym `downgrade`. Test w CI: `upgrade head`
   i `downgrade base` na czystej bazie w kontenerze (bramka G2, sprawdzenie `migration`).
4. **Klucze i czas:**
   - klucze wewnętrzne `bigint generated always as identity`; identyfikatory widoczne na
     zewnątrz (API) to UUIDv7, żeby nie zdradzać liczności i nie ułatwiać zgadywania (IDOR);
   - każdy znacznik czasu to `timestamptz` w UTC; szeregi czasowe mają klucz
     `(instrument_id, ts)` oraz kolumny `source` i `ingested_at` (roadmapa);
   - dane cech i dowodów mają `as_of` (chwila, której dotyczą) i `data_cutoff` (najpóźniejsza
     dana użyta do obliczenia), co pozwala sprawdzić brak zaglądania w przyszłość (G5).
5. **Liczby:** ceny, wolumeny, kwoty i stawki finansowania jako `numeric` (bez utraty
   dokładności względem źródła i w rozliczeniach bota); prawdopodobieństwa, kwantyle i metryki
   modeli jako `double precision`. Obliczenia analityczne działają na kopiach w Polars/DuckDB.
6. **Hypertable (TimescaleDB):** `candles`, `candles_ref`, `trades_agg_1m`, `funding_rates`,
   `open_interest`, `orderbook_top`, `feature_values`. Kompresja danych starszych niż 90 dni
   (Fundamenty, przepływ 6). Pozostałe tabele są zwykłe.
7. **JSONB tylko tam, gdzie struktura jest wersjonowana:** `evidence.facts` i ładunki zdarzeń
   mają `schema_version` i JSON Schema (ADR-0003, kontrakt `Evidence` v1); żadnych „worków na
   wszystko”.
8. **Audyt tylko do dopisywania:** `audit_log` bez `UPDATE` i `DELETE` dla ról aplikacji
   (odebrane uprawnienia + wyzwalacz odrzucający zmiany, także dla właściciela tabeli poza
   migracją).
9. **Role bazy (najmniejsze uprawnienia):**

   | Rola                | Kto                                    | Uprawnienia                                                                                                            |
   | ------------------- | -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
   | `goatcash_migrator` | tylko migracje (Alembic)               | właściciel obiektów, DDL                                                                                               |
   | `goatcash_app`      | `api`, `worker`, `scheduler`, `ingest` | DML w `public` (bez zmian w `audit_log`); w `bot`: zapis `order_intents`, odczyt stanu bota, **bez** kolumn z kluczami |
   | `goatcash_auth`     | Better Auth w `apps/web`               | tylko tabele Better Auth i odczyt ról                                                                                  |
   | `goatcash_executor` | `executor`                             | tylko schemat `bot`                                                                                                    |
   | `goatcash_readonly` | analizy, kopie, Grafana                | `SELECT` bez danych osobowych i bez `bot.exchange_connections`                                                         |

10. **Tabele dodane ponad listę z roadmapy (jawne rozszerzenia):** `event_outbox` (wysyłka
    zdarzeń w tej samej transakcji co zapis, ADR-0003) oraz tabele wtyczek Better Auth
    `two_factor`, `passkey`, `jwks` (ADR-0004).

## Rozważane alternatywy

| Opcja                                        | Za                                        | Przeciw                                                                                 |
| -------------------------------------------- | ----------------------------------------- | --------------------------------------------------------------------------------------- |
| `double precision` także dla cen             | mniej miejsca, szybsze agregacje          | błędy zaokrągleń w rozliczeniach i porównaniach ze źródłem; dwa typy dla tej samej ceny |
| Osobna baza dla bota                         | najmocniejsza izolacja                    | dwie instancje na jednej VM (RAM), kopie i migracje razy dwa; schemat + role wystarczą  |
| Autogenerate Alembic jako źródło migracji    | szybko                                    | nie widzi hypertable, wyzwalaczy, uprawnień; ciche różnice                              |
| Osobny magazyn szeregów (ClickHouse, Influx) | szybsze zapytania na bardzo dużych danych | kolejny silnik do utrzymania; skala projektu mieści się w TimescaleDB                   |
| Identyfikatory UUID wszędzie                 | jeden typ                                 | większe indeksy w hypertable; `bigint` wewnątrz + UUIDv7 na zewnątrz łączy zalety       |

## Konsekwencje

- Migracja 0001 (PR `feat/E2-migracja-0001`) tworzy wszystkie grupy tabel, schemat `bot`, role
  i wyzwalacz `audit_log`; test sprawdza też, że hypertable istnieją i że `goatcash_app` nie
  może zmienić `audit_log` ani odczytać kluczy w `bot.exchange_connections`.
- Każdy kolejny etap zmienia schemat wyłącznie migracją z testem w obie strony.
- Sprawdzimy decyzję w G4/G5: kompletność danych ≥ 99,9%, test point-in-time 100%, rozmiar bazy
  po 30 dniach ingestu w budżecie wolumenu (raport w E5).
