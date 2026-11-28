# Bramka pracy G5p (E5, ścieżka pracy inżynierskiej): raport

- **Status:** ZALICZONA 27.11.2026 (dowód `ci`: [`G5p.passed.json`](G5p.passed.json),
  sprawdzany przez `gate-guard`). Zamyka zakres pracy E5; reszta E5 (pełna bramka G5):
  ⏸ ścieżka produktu.
- **Kryteria (`testy.md`, sekcja 3a, wiersz G5p; ADR-0008):** 100% cech `fs-1p` przechodzi
  test point-in-time (Hypothesis, 1000 losowych chwil: dane obcięte do t = pełne dane
  w chwili t); wartości referencyjne liczone niezależnie, różnica < 1e-9 po okresie
  rozgrzewki; luka w danych daje `NaN` ze statusem; dwa pełne przeliczenia historii
  identyczne bit w bit. Wymagania F-07, F-08 (`work_target` w `docs/wymagania.yaml`).
- **Definicja automatu:** [`gates/G5p.yaml`](../../gates/G5p.yaml), uruchomienie
  `make gate G=5p`. Od zamknięcia E5 job „8 bramka G5p” jest w macierzy joba `gate`
  i w `ci-ok` (ochrona przed regresją), jak G1–G4p.
- **Zaliczenie (dowód `ci`):** zielony job „8 bramka G5p (ubuntu-latest)” w przebiegu
  `ci.yml` na `main`. G5p nie ma kryterium na staging (decyzja 3 niżej).

## Dowód (G5p.passed.json)

| Część | Przebieg                              | Commit    | Wynik                                                                                   |
| ----- | ------------------------------------- | --------- | --------------------------------------------------------------------------------------- |
| CI    | `ci.yml` 46053939823 (push na `main`) | `aab1d77` | job „8 bramka G5p (ubuntu-latest)” zielony: 6 PASS, 0 FAIL (macOS: 5 PASS, 1 SKIP bazy) |

Dowód i dokumenty są w jednym PR (jak przy G4p): część CI pochodzi z przebiegu na `main`
sprzed tego PR, w którym job G5p (wtedy `gate-next`) był już zielony.

Plik dowodu utworzył `scripts/gate_pass.py 5p --run 46053939823` (27.11.2026), z tym samym
podstawionym `gh` dla `repo view` co przy G4p (GraphQL zablokowany w sesji; `docs/gates/G4p.md`,
lekcja E4). Skrypt i reguły bez zmian; dowód sprawdza niezależnie `gate-guard`.

Wcześniejsze przebiegi G5p: w PR #133 (46035586059 i 46045475728: 5 PASS, 1 FAIL, celowo czerwone
`database` przed PR 2), w PR #134 i na `main` po jego scaleniu: 6/6.

## Podział E5 na PR-y (zaakceptowany przez właściciela 27.11.2026)

| PR  | Gałąź                    | Zakres                                                                                                                                                                                       | Stan      |
| --- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| 1   | `claude/E5-cechy-fs1p`   | Polars, TA-Lib (tylko testy), `MarketView(as_of, known_at)`, 19 cech `fs-1p` z oknem i źródłami, hash definicji, statusy braków; testy point-in-time, wartości referencyjne, luki, bit w bit | ✅ #133   |
| 2   | `claude/E5-magazyn-cech` | migracja 0004 (klucz `(asset_id, quote_asset_id)`, `status`), zapis `feature_sets` i `feature_values`, zadanie po `candle.closed` → `features.ready` v2, przeliczenie wsadowe; testy w bazie | ✅ #134   |
| 3   | `claude/E5-g5p`          | G5p do macierzy `gate`, ten raport z dowodami, wzory w `metody.md`, dokumentacja etapu i `G5p.passed.json` (CI na `main` sprzed tego PR, jak G4p)                                            | ✅ ten PR |

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
- **Tolerancja:** różnica bezwzględna < 1e-9 dla każdej cechy, dokładnie jak w kryterium
  (od audytu 28.11.2026; wcześniej 1e-9 · max(1, |wzorcowa|), patrz „Audyt E5”); cecha ma
  wartość (`ok`) dokładnie tam, gdzie wzorzec ją ma (to samo okno rozgrzewki).
- **Inicjalizacja rekurencji jak w TA-Lib** (EMA od średniej prostej pierwszych n wartości,
  ATR, RSI i ADX z wygładzaniem Wildera i sumami startowymi z `ta_ADX.c`), więc zgodność
  z TA-Lib obowiązuje od pierwszej wartości. Jedno jawne odejście: RSI przy płaskiej cenie
  (brak zysków i strat w oknie) = 50, a nie 0 jak w TA-Lib.
- **MACD** to EMA12 − EMA26 z EMA jak w `talib.EMA`; funkcja `talib.MACD` zaczyna szybką EMA
  inaczej, więc różni się od naszej definicji na początku odcinka (rzędu 1e-4..1e-2
  w skali `macd_rel`) i zbiega do < 1e-9 po 130 h (test
  `test_macd_definition_vs_talib_macd_function`). Wzorcem dla `macd_rel` i `macd_hist_rel`
  są EMA z TA-Lib, nie funkcja `talib.MACD`.
- **Niezależność wzorców:** TA-Lib to niezależna implementacja arytmetyki. Dla zwrotów,
  zmienności, z-score, Donchiana i wolumenu wzorzec z TA-Lib jest złożony z jej funkcji
  podstawowych według tych samych wzorów, a wersję w czystym Pythonie napisał ten sam autor
  według tych samych konwencji; same wzory potwierdzają przykłady policzone ręcznie.
- **Dane:** losowe serie (3 ziarna × 3 pary × 700 h) i prawdziwa cena referencyjna z kaset E4
  (mediana OKX i Bybit, 5 par × 2000 h od 2024-07-01), do tego przykłady policzone ręcznie.

## Wyniki (przebieg 46053939823, job „8 bramka G5p (ubuntu-latest)”)

| Sprawdzenie     | Wynik                                                                                                                                                                                                                                                                                                                      |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `point-in-time` | PASS (67 s): 1000 losowych chwil (także w środku godziny), 3 pary z lukami, późnym zapisem i notowaniem od 80 h: wszystkie 19 cech bit w bit równe pełnemu przeliczeniu, każda cecha z wartością `ok` w ≥ 100 chwilach; replay `known_at` (300 chwil); zmiana danych z przyszłości (200 chwil); 5 mutacji wykrytych (F-07) |
| `reference`     | PASS (5 s): TA-Lib i czysty Python, 3 ziarna × 3 pary × 700 h i prawdziwa cena referencyjna OKX + Bybit (5 par × 2000 h): \|różnica\| ≤ 1e-9 · max(1, \|wzorzec\|), wartość dokładnie tam, gdzie wzorzec; przykłady ręczne (RSI 66,67; ADX 100; %B 0,75; korelacja ±1 i inne)                                              |
| `gaps`          | PASS (2 s): luka i zła DQ obu giełd (`PairDq` E4) → `missing_data` i NaN; po luce wartości bit w bit jak z danych tylko po luce; mutacja „wypełnij poprzednią świecą” wykryta; okno deklarowane = pierwsza wartość                                                                                                         |
| `determinism`   | PASS (7 s): dwa pełne przeliczenia (syntetyczne i prawdziwe dane) z tym samym SHA-256 bitów; osobny proces z `POLARS_MAX_THREADS=1` ten sam; wersja `fs-1p` = `66ce07b92a443614`, każda zmiana definicji zmienia wersję (F-08)                                                                                             |
| `database`      | PASS (55 s): Postgres 17 z Timescale i Valkey 9; przeliczenie 5 par × 2000 h zapisane rolą `goatcash_app` i odczytane = przeliczenie w pamięci (SHA-256), drugie przeliczenie: 0 zmian; `features.ready` v2 zgodne z kontraktem, `correlation_id` = `candle.closed`; konsument: XACK po skutku, dead-letter po 5 próbach   |

Na macOS (`macos-15`, arm64, TA-Lib 0.8.3 z wheela): 5 PASS, `database` SKIP (brak Dockera
na runnerach macOS). Wartości z TA-Lib i test point-in-time przechodzą na obu systemach.

## Uproszczenia ścieżki pracy i jawne decyzje

- **Doprecyzowanie `MarketView`** (decyzja 2): `ts + 1 h ≤ as_of` zawsze, `ingested_at ≤ known_at`
  tylko w replay okresu na żywo; opis w `docs/praca/metody.md`, sekcja 2.
- **Tolerancja wartości referencyjnych:** od audytu 28.11.2026 dokładnie jak w kryterium
  (różnica bezwzględna < 1e-9). Dowód G5p (46053939823) powstał jeszcze ze słabszym progiem
  dla RSI i ADX; przebieg z poprawionym progiem: PR audytu.
- **Replay z `known_at` przy poprawionych świecach (ograniczenie z E4):** upsert ceny
  referencyjnej w E4 nadpisuje `ingested_at` (`marketdata/_impl/pgstore.py`), więc replay
  sprzed aktualizacji widzi lukę zamiast wcześniejszej wersji świecy. Bez zaglądania
  w przyszłość, ale nie dokładnie „jak wiedzieliśmy wtedy”; rozwiązanie do decyzji przed
  workerem w E7 (`docs/stan-pracy.md`, otwarte sprawy).
- **Dowód w PR zamykającym:** jak przy G4p, część CI dowodu pochodzi z przebiegu na `main`
  sprzed PR zamykającego (job „8 bramka G5p” był wtedy w `gate-next`), a plik dowodu jest
  w tym samym PR; procedura w `docs/start-nowej-rozmowy.md` mówi o pliku po scaleniu.
  Jawne odstępstwo (bez wpływu na wiarygodność: `gate-guard` sprawdza przebieg, commit
  i job). Po scaleniu PR zamykającego G5p w macierzy `gate` też jest zielona: 46130500409.
- **RSI przy płaskiej cenie = 50** (TA-Lib: 0). Jedyne odejście od wzorca; wartość
  neutralna zamiast „skrajnie wyprzedany”.
- **Bit w bit zamiast tolerancji 1e-9** (F-08, `work_target`): test sprawdza identyczność
  bitów, mocniej niż próg z wymagania.
- **„Live vs replay”:** w ścieżce pracy miniatura w teście (cechy liczone godzina po
  godzinie po każdym `candle.closed` = pełne przeliczenie, bit w bit); 7 dni na staging:
  produkt. Worker na staging od E7 (decyzja 3), więc `feature_values` na staging jest puste.

## Audyt E5 (28.11.2026)

Audyt na prośbę właściciela (asystent sprawdzał własną pracę z rozmowy E5, więc nie jest to
recenzja niezależna). Mutacje w kopii kodu: 15 z 15 wykrytych (przeciek otwartej świecy,
`known_at` pominięty, NaN → 0, luka jako rozgrzewka, okno EMA o 1, szum 1 ulp, korelacja
BTC = 1, upsert bez wykrycia zmiany, zapis jako `real`, `XACK` przed skutkiem i inne).
Znalezione luki i poprawki (PR audytu):

| Luka                                                                                                                                            | Poprawka                                                                              |
| ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Próg wartości referencyjnych 1e-9 · max(1, \|b\|) przepuszczał odchylenie RSI o 1,5e-8                                                          | próg bezwzględny < 1e-9 (`fs_helpers.py`); RSI + 5e-9 i ADX · (1 + 1e-10) wykryte     |
| 6 z 1000 chwil na pełnej godzinie; mutację „świeca zamknięta w as_of odrzucona” wykrywał tylko jeden test                                       | połowa chwil na pełnej godzinie, asercja ≥ 300; mutacja wykryta przez test 1000 chwil |
| MACD porównany z EMA z TA-Lib, nie z `talib.MACD` (różnica na starcie 1e-3)                                                                     | definicja opisana, test różnicy i jej wygaśnięcia po 130 h                            |
| `ingested_at` nadpisywane przez upsert E4: replay `known_at` niewierny dla poprawionych świec                                                   | opis ograniczenia; decyzja przed E7                                                   |
| Dowód z przebiegu sprzed PR zamykającego, bez zapisu odstępstwa                                                                                 | zapis wyżej                                                                           |
| ADR-0003 bez `correlation_id` w outbox i filtra typów w przekaźniku; brak lekcji o usuniętej gałęzi; `metody.md` bez źródeł cech i ID przebiegu | dopisane                                                                              |

**NIESPRAWDZONE w audycie:** to, że w CI uruchomił się konkretnie `test_migration_0004.py`
(log bramki G2 pokazuje tylko wynik zbiorczy, artefakty niedostępne z sesji).

## Przechodzi do ścieżki produktu (pełna G5)

Pozostałe cechy do ok. 60 w `fs-1` (wymagają danych z pełnego E4), eksport miesięczny
Parquet na R2, retencja i kompresja, test live vs replay przez 7 dni, wydajność 150 par
≤ 60 s (pełne przeliczenie czyta teraz całą historię pary; dla 150 par potrzebny stan
przyrostowy).
