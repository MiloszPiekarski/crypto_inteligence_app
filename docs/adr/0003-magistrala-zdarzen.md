# ADR-0003: Magistrala zdarzeń (Valkey Streams)

- **Status:** proponowana (zatwierdzenie: scalenie PR `docs/E2-adr`)
- **Data:** 2026-11-22
- **Etap:** E2
- **Źródło:** roadmapa E2 („Kontrakty”), Fundamenty sekcja 2 (procesy, przepływy 1–5), ADR-0001

## Kontekst

Procesy `ingest`, `worker`, `scheduler`, `api` i `web` reagują na zdarzenia (zamknięta świeca,
gotowe cechy, nowy dowód agenta, ocena, narracja, alert, intencja zlecenia). Zdarzenie nie może
zginąć ani zostać przetworzone dwa razy z innym skutkiem, a przy awarii Valkey dane w Postgresie
muszą pozostać spójne. Valkey jest już w stosie (ADR-0001) i nie jest widoczny z internetu.

## Decyzja

1. **Valkey Streams**, jeden strumień na typ zdarzenia: `ev:<typ>` (np. `ev:candle.closed`).
   Typy z roadmapy: `candle.closed`, `features.ready`, `evidence.published`,
   `assessment.updated`, `narrative.ready`, `alert.triggered`, `order_intent.created`,
   `order.updated`.
2. **Koperta każdego komunikatu** (JSON Schema w `packages/contracts/events/`, PR
   `feat/E2-schematy-zdarzen`):
   `event_id` (UUIDv7), `type`, `schema_version` (liczba całkowita), `occurred_at` (UTC),
   `producer` (proces i wersja), `correlation_id`, `payload` (schemat per typ).
   Zmiana niezgodna wstecz = nowy `schema_version`; konsument obsługuje bieżącą i poprzednią.
3. **Postgres jest źródłem prawdy, strumień tylko powiadamia.** Zdarzenie wynikające z zapisu
   do bazy trafia najpierw do tabeli `event_outbox` w **tej samej transakcji** co zapis
   (transactional outbox), a proces przekaźnika publikuje je do strumienia i oznacza jako
   wysłane. Brak „podwójnego zapisu” baza + Valkey bez transakcji.
4. **Dostarczanie co najmniej raz:** grupy konsumentów (`XREADGROUP`), potwierdzenie `XACK`
   dopiero po skutku; konsumenci są idempotentni (klucz `event_id`, zapis wyniku z
   `ON CONFLICT DO NOTHING`). Wiadomości zawieszone dłużej niż 60 s przejmuje inny konsument
   (`XAUTOCLAIM`); po 5 nieudanych próbach komunikat trafia do `ev:dead-letter` z powodem
   i jest widoczny w alertach.
5. **Retencja:** `MAXLEN ~` dobrana tak, żeby strumień mieścił co najmniej 7 dni ruchu; historię
   ma Postgres, więc utrata strumienia oznacza tylko ponowną publikację z `event_outbox`.
6. **Kolejki zadań (arq) to osobny mechanizm** dla pracy do wykonania (obliczenia, narracje,
   backtesty), a strumienie są dla faktów, które się wydarzyły.
7. **Executor nie korzysta z Valkey** (ADR-0006): intencje zleceń pobiera z Postgresa, a
   `order_intent.created` i `order.updated` służą interfejsowi i alertom.

## Rozważane alternatywy

| Opcja                             | Za                              | Przeciw                                                                 |
| --------------------------------- | ------------------------------- | ----------------------------------------------------------------------- |
| Pub/Sub Valkey                    | najprostsze                     | brak trwałości i potwierdzeń: zdarzenie przy braku słuchacza ginie      |
| Postgres `LISTEN/NOTIFY` + outbox | jeden silnik                    | brak grup konsumentów i ponowień; ładunek do 8 kB                       |
| Kafka / Redpanda / NATS JetStream | dojrzałe strumienie, replikacja | kolejny serwis i pamięć na jednej VM; skala tego nie wymaga             |
| Publikacja bez outboxa            | mniej kodu                      | zapis w bazie bez zdarzenia (albo odwrotnie) przy awarii między krokami |

## Konsekwencje

- Tabela `event_outbox` w migracji 0001 (jawne rozszerzenie listy tabel, ADR-0002).
- Testy kontraktowe zdarzeń (G2, sprawdzenie `event-schemas`): poprawne komunikaty przechodzą,
  błędne są odrzucane; producenci i konsumenci walidują ładunek względem schematu (testy.md).
- W E7/E13 test: zabity konsument w trakcie przetwarzania → komunikat przejęty i przetworzony
  dokładnie raz w skutkach (G13: „dokładnie raz” dla alertów).
- Metryki: opóźnienie konsumentów, długość `pending`, liczba w `ev:dead-letter` (Grafana).
