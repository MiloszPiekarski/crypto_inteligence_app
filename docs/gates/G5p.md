# Bramka pracy G5p (E5, ścieżka pracy inżynierskiej): raport

- **Status:** W TOKU (od 27.11.2026). Bramka jest czerwona, dopóki nie ma zapisu cech
  w Postgresie (sprawdzenie `database`, `make features-db-test`: PR 2 E5).
- **Kryteria (`testy.md`, sekcja 3a, wiersz G5p; ADR-0008):** 100% cech `fs-1p` przechodzi
  test point-in-time (Hypothesis, 1000 losowych chwil: dane obcięte do t = pełne dane
  w chwili t); wartości referencyjne liczone niezależnie, różnica < 1e-9 po okresie
  rozgrzewki; luka w danych daje `NaN` ze statusem; dwa pełne przeliczenia historii
  identyczne bit w bit. Wymagania F-07, F-08 (`work_target` w `docs/wymagania.yaml`).
- **Definicja automatu:** [`gates/G5p.yaml`](../../gates/G5p.yaml), uruchomienie
  `make gate G=5p` (lokalnie i w CI, job „8 bramka G5p” poza `ci-ok`, dopóki G5p nie jest
  zaliczona).
- **Zaliczenie (dowód `ci`):** zielony job „8 bramka G5p (ubuntu-latest)” w przebiegu
  `ci.yml` na `main`. G5p nie ma kryterium na staging (decyzja 3 niżej).

## Podział E5 na PR-y (zaakceptowany przez właściciela 27.11.2026)

| PR  | Gałąź                    | Zakres                                                                                                                                                                                       | Stan      |
| --- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| 1   | `claude/E5-cechy-fs1p`   | Polars, TA-Lib (tylko testy), `MarketView(as_of, known_at)`, 19 cech `fs-1p` z oknem i źródłami, hash definicji, statusy braków; testy point-in-time, wartości referencyjne, luki, bit w bit | ✅ #133   |
| 2   | `claude/E5-magazyn-cech` | migracja 0004 (klucz `(asset_id, quote_asset_id)`, `status`), zapis `feature_sets` i `feature_values`, zadanie po `candle.closed` → `features.ready` v2, przeliczenie wsadowe; testy w bazie | ⏳ ten PR |
| 3   | `claude/E5-g5p`          | G5p do macierzy `gate`, ten raport z dowodami, wzory w `metody.md`, dokumentacja etapu; potem mały PR z `G5p.passed.json`                                                                    | ⬜        |

## Zmiany poza modułem `features` (PR 2)

- **`event_outbox.correlation_id`** (migracja 0004): `features.ready` niesie w kopercie
  identyfikator `candle.closed`, które je wywołało (ADR-0003, pole `correlation_id`).
- **Przekaźnik outbox z filtrem typów** (`relay_outbox(..., types=...)`): każdy proces
  publikuje tylko własne zdarzenia pod własną nazwą `producer` (ingest `candle.closed`,
  worker `features.ready`). Bez filtra ingest publikowałby też `features.ready` jako
  `ingest@…`.
- **Kontrakt `features.ready` v2** obok v1 (ADR-0003: nowa wersja przy zmianie niezgodnej
  wstecz); test kontraktów obsługuje wersje schematów.

## Decyzje właściciela 27.11.2026

Zapis w karcie E5 (`roadmapa.md`, „Ścieżka pracy inżynierskiej”):

1. Klucz cech `(asset_id, quote_asset_id)` i kolumna `status` w `feature_values`;
   `features.ready` w `schema_version 2`.
2. `MarketView(as_of, known_at=None)`: `ts + 1 h ≤ as_of` zawsze, `ingested_at ≤ known_at`
   tylko w replay okresu na żywo (`docs/praca/metody.md`, sekcja 2).
3. Worker na staging dopiero w E7 (kod i testy w E5).
4. Korelacja BTC z BTC: `NaN` ze statusem `not_applicable`.

## Jak liczone są wartości referencyjne

- **Dwie niezależne implementacje:** TA-Lib 0.8.3 (biblioteka C; tylko w testach, wheele dla
  Linuksa i macOS arm64, CI na obu systemach) i czysty Python na pętlach z `math.fsum`
  (`services/platform/tests/features/reference.py`, bez kodu z modułu `features`).
- **Tolerancja:** |nasza − wzorcowa| ≤ 1e-9 · max(1, |wzorcowa|), po okresie rozgrzewki;
  cecha ma wartość (`ok`) dokładnie tam, gdzie wzorzec ją ma (to samo okno rozgrzewki).
- **Inicjalizacja rekurencji jak w TA-Lib** (EMA od średniej prostej pierwszych n wartości,
  ATR, RSI i ADX z wygładzaniem Wildera i sumami startowymi z `ta_ADX.c`), więc zgodność
  z TA-Lib obowiązuje od pierwszej wartości. Jedno jawne odejście: RSI przy płaskiej cenie
  (brak zysków i strat w oknie) = 50, a nie 0 jak w TA-Lib.
- **Dane:** losowe serie (3 ziarna × 3 pary × 700 h) i prawdziwa cena referencyjna z kaset E4
  (mediana OKX i Bybit, 5 par × 2000 h od 2024-07-01), do tego przykłady policzone ręcznie.

## Dowody (uzupełniane przy domknięciu etapu)

⬜ Przebieg CI na `main` z zielonym jobem „8 bramka G5p (ubuntu-latest)”: po PR 3.
