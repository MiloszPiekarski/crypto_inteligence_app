# Bramka pracy G4p (E4, ścieżka pracy inżynierskiej): raport

- **Status:** ZALICZONA 27.11.2026 (dowód `mixed`: [`G4p.passed.json`](G4p.passed.json),
  sprawdzany przez `gate-guard`). Zamyka zakres pracy E4; reszta E4 (pełna bramka G4):
  ⏸ ścieżka produktu.
- **Kryteria (`testy.md`, sekcja 3a, wiersz G4p; ADR-0008):** normalizacja na nagranych
  odpowiedziach: 100% zgodności pól i typów; DQ wykrywa ≥ 95% z 200 wstrzykniętych błędów
  przy fałszywych alarmach < 1%; obsługa 429, przerwania i wznowienia uzupełniania historii
  (testy z atrapami); **staging:** 100% luk wykrytych i opisanych przez detektor (po stronie
  giełdy albo nasza) i kompletność ≥ 99,9% względem świec, które giełda faktycznie
  udostępnia, dla 20 par od 2023-01-01. Wymagania F-04, F-05, F-06 (`work_target`
  w `docs/wymagania.yaml`).
- **Definicja automatu:** [`gates/G4p.yaml`](../../gates/G4p.yaml), uruchomienie
  `make gate G=4p`. Od zamknięcia E4 job „8 bramka G4p” jest w macierzy joba `gate`
  i w `ci-ok` (ochrona przed regresją), jak G1–G3.
- **Zaliczenie (dowód mixed, jak G3):** zielony job „8 bramka G4p (ubuntu-latest)”
  w przebiegu `ci.yml` na `main` **oraz** zielony przebieg `data-report.yml` na `main`
  z commitu nie starszego (blok `evidence` w `gates/G4p.yaml`). Bramka pracy nie przyjmuje
  dowodu `local`.

## Dowód (G4p.passed.json)

| Część       | Przebieg                                | Commit    | Wynik                                                                                       |
| ----------- | --------------------------------------- | --------- | ------------------------------------------------------------------------------------------- |
| CI          | `ci.yml` 45973429769 (push na `main`)   | `cadf19b` | job „8 bramka G4p (ubuntu-latest)” zielony: 6 PASS, 0 FAIL (macOS: zielony)                 |
| data-report | `data-report.yml` 45981882350 (ręcznie) | `cadf19b` | `RAPORT WYNIK: OK`: 40/40 instrumentów, 1 369 338 świec, 0 brakujących bez opisu, min. 100% |

Plik dowodu utworzył `scripts/gate_pass.py 4p --run 45973429769 --workflow
data-report=45981882350` (27.11.2026). W sesji asystenta GraphQL GitHuba jest zablokowany,
a skrypt odczytuje nazwę repozytorium przez `gh repo view` (GraphQL): na czas tej komendy
asystent podstawił `gh`, które na `repo view` zwraca `MiloszPiekarski/crypto_inteligence_app`,
a pozostałe wywołania (sprawdzenie przebiegów przez REST) przekazuje do prawdziwego `gh`.
Skrypt i reguły bez zmian; dowód sprawdza niezależnie `gate-guard`.

Wcześniejsze przebiegi `data-report.yml` na tym samym commicie: 45978318446 i 45981033680
(czerwone: historia jeszcze się pobierała; raport poprawnie wskazał pary bez danych
i „dane nieaktualne”). Pierwsze pobranie całej historii (20 par x 2 giełdy od 2023-01-01)
zajęło ok. 60 min po wdrożeniu `ingest` (`deploy-staging.yml` 45973430326).

## Podział E4 na PR-y (zaakceptowany przez właściciela 26.11.2026)

| PR  | Gałąź                        | Zakres                                                                                                                                                                       | Stan      |
| --- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| 1   | `claude/E4-marketdata-rdzen` | `MarketDataSource`, adaptery OKX i Bybit (ccxt), normalizacja, uniwersum 20 par, DQ, detektor luk, cena referencyjna, `candle.closed` (outbox), punkty kontrolne, testy, G4p | ✅ #129   |
| 2a  | `claude/E4-sonda-gield`      | `marketdata-probe.yml` i polecenie `probe`: sonda dostępu z Amsterdamu, nagranie kaset Bybit (podział PR 2 na 2a i 2b: zgoda właściciela 27.11.2026)                         | ✅ #130   |
| 2b  | `claude/E4-ingest-staging`   | kasety Bybit, proces `ingest` w Compose staging, `data-report.yml`, poprawka podpisów w `CLAUDE.md`                                                                          | ✅ #131   |
| 3   | `claude/E4-g4p`              | G4p do macierzy `gate`, ten raport z dowodami, dokumentacja etapu                                                                                                            | ✅ ten PR |

## Wybór giełd

Giełda główna **OKX**, druga **Bybit** (propozycja z rozmowy 26.11.2026, zaakceptowana):
obie mają te same pary spot `*/USDT` i historię 1 h przez REST od 2023 (OKX
`/api/v5/market/history-candles`, 100 świec na zapytanie; Bybit `/v5/market/kline`, 1000).
Odrzucone: Kraken (REST OHLC zwraca tylko ostatnie 720 świec, bez historii od 2023),
Coinbase (mało par USDT, cena referencyjna wymaga tej samej pary na obu giełdach).

Dostęp sprawdzony 26.11.2026:

| Skąd                       | OKX                                                                                            | Bybit                                                                        |
| -------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| sesja asystenta w chmurze  | HTTP 200; 20/20 par spot, pierwsza świeca 1 h każdej pary = 2023-01-01 00:00 UTC               | HTTP 403 („CloudFront … block access from your country”)                     |
| serwer staging (Amsterdam) | HTTP 200; 20/20 par, pierwsza świeca 2023-01-01 00:00 UTC (`marketdata-probe.yml` 45917575053) | HTTP 200; 20/20 par, pierwsza świeca 2023-01-01 00:00 UTC (ten sam przebieg) |
| GitHub Actions             | nie dotyczy: CI testuje na kasetach, bez sieci                                                 | nie dotyczy                                                                  |

## Uproszczenia ścieżki pracy i jawne decyzje

- **CoinGecko bez API w czasie działania** (decyzja właściciela 26.11.2026): metadane
  20 par (symbol, nazwa, `coingecko_id`) zapisane raz w
  `services/platform/src/goatcash/marketdata/config/universe.toml`, ze źródłem i datą
  w komentarzu (odczyt CoinGecko `/coins/markets` 26.11.2026). Bez klucza, bez SOPS.
- **Kasety Bybit z serwera w Amsterdamie:** Bybit blokuje kraj sesji asystenta (403
  CloudFront), więc kasety Bybit nagrała sonda na serwerze staging (`marketdata-probe.yml`
  45917575053, obraz `sha-ab9dae6`, 27.11.2026): 26 plików, archiwum SHA-256
  `82ae3965207f39a60aeba2c4c076ec79175c2810642d28a5436c39d4e90871a1`, wypisane w logu
  przebiegu i rozpakowane do `services/platform/tests/marketdata/fixtures/bybit/` (PR 2b).
- **Proces `ingest` bez nowego sekretu:** adres bazy z `api.env`, po połączeniu `SET ROLE
  goatcash_app` (raport: `goatcash_readonly`); `GOATCASH_INGEST_PAUSED=1` wstrzymuje
  zapytania do giełd (test Compose w CI). Raport i sonda łączą się kluczem wdrożeń
  (środowisko `staging`, tylko `main`), ze stałym poleceniem zdalnym.
- **Lista instrumentów w kasecie przycięta do 20 par** (pełna odpowiedź OKX ma 1,5 MB);
  świece zapisane dosłownie.
- **Świece przez API niejawne ccxt**, nie `fetch_ohlcv`: `fetch_ohlcv` zamienia ceny na
  float, a normalizacja wymaga `Decimal` z tekstu odpowiedzi. ccxt daje transport,
  ograniczanie tempa, mapowanie błędów (429 → `RateLimitExceeded`) i opis rynków.
- **Nieaktualność danych: 2 h** (REST co godzinę; „3 min” z pełnego zakresu dotyczy
  websocketów w ścieżce produktu).
- **`candle.closed` tylko dla świec z ostatniej doby**: historia od 2023 nie zalewa
  strumienia (konsumenci czytają historię z Postgresa, ADR-0003); zdarzenie przez
  `event_outbox` w tej samej transakcji co świeca.
- **Migracja 0003:** tabela `ingest_checkpoints` (punkty kontrolne, zapis w transakcji
  okna) i kolumny precyzji `instruments.price_tick`, `instruments.amount_step` (schemat
  0001 nie miał miejsca na precyzję z punktu 2 roadmapy).
- **Klasyfikacja luk w `dq_events`** bez zmiany schematu: `kind = gap_exchange`
  (`decision = flagged`) albo `gap_ours` (`decision = repaired`), zakres w `details`
  (`end`, `count`).

## Wyniki

| Kryterium                                   | Sprawdzenie                  | Wynik                                                                                                                                                   |
| ------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Normalizacja 100% (obie giełdy, 20 par)     | `normalization` (CI)         | ✅ OKX i Bybit: 20/20 par, każde pole i typ zgodne z surowym JSON giełdy (wartości dziesiętne co do zapisu)                                             |
| DQ ≥ 95% z 200 błędów, fałszywe alarmy < 1% | `dq-injection` (CI)          | ✅ wykrycie 200/200 (każdy z 7 rodzajów 100%), fałszywe alarmy 0%; prawdziwe dane: 0,11% (OKX sam), 0/20 000 (OKX + Bybit)                              |
| 429, przerwanie, wznowienie                 | `resilience` (CI)            | ✅ 429 i błąd sieci ponawiane (1, 2, 4 s…), awaria w dowolnym oknie: wznowienie = stan bez awarii (Hypothesis)                                          |
| Poprawność analityczna (luki, cena ref.)    | `analytics`, `database` (CI) | ✅ wartości referencyjne, właściwości, brak zaglądania w przyszłość; Postgres (rola `goatcash_app`) = magazyn w pamięci; raport z rolą tylko do odczytu |
| 100% luk opisanych, kompletność ≥ 99,9%     | `data-report.yml` na staging | ✅ 0 brakujących świec bez opisu, kompletność 100% dla 40/40 instrumentów od 2023-01-01 00:00 UTC                                                       |
| F-06: cena referencyjna dla 100% świec      | `data-report.yml` na staging | ✅ 0 chwil z poprawną świecą bez ceny referencyjnej                                                                                                     |

**Luki w danych.** Na prawdziwych danych z 2023-01-01 do 2026-11-27 detektor nie znalazł
żadnej brakującej świecy 1 h na OKX ani na Bybit dla 20 par (0 luk po stronie giełdy,
0 naszych, 0 świec odrzuconych przez DQ). Kryterium „100% luk wykrytych i opisanych” jest
więc spełnione przez brak luk; działanie detektora i klasyfikacji (po stronie giełdy,
nasza, odrzucona) pokazują testy na atrapach (`test_ingest.py`, `test_pgstore.py` na
Postgresie, `test_runtime.py`). Proces `ingest` co godzinę uruchamia detektor dla każdej
pary, więc luka powstała w przyszłości trafi do `dq_events` z klasyfikacją.

**Raport z przebiegu dowodowego (`data-report.yml` 45981882350).** Kolumna „do” to punkt
kontrolny (koniec przetworzonego przedziału); część par miała już drugi cykl godzinowy.

| giełda | para      | od               | do               | oczekiwane | zapisane | luki giełdy | odrzucone | bez opisu | kompletność | bez ceny ref. | uwagi |
| ------ | --------- | ---------------- | ---------------- | ---------: | -------: | ----------: | --------: | --------: | ----------: | ------------: | ----- |
| okx    | BTC-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | BTC-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | ETH-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | ETH-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | SOL-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | SOL-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | XRP-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | XRP-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | DOGE-USDT | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | DOGE-USDT | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | ADA-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | ADA-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | LTC-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | LTC-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | LINK-USDT | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | LINK-USDT | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | DOT-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | DOT-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | AVAX-USDT | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | AVAX-USDT | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | TRX-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | TRX-USDT  | 2023-01-01T00:00 | 2026-11-27T09:00 |      34233 |    34233 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | BCH-USDT  | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | BCH-USDT  | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | ATOM-USDT | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | ATOM-USDT | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | XLM-USDT  | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | XLM-USDT  | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | UNI-USDT  | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | UNI-USDT  | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | ETC-USDT  | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | ETC-USDT  | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | FIL-USDT  | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | FIL-USDT  | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | NEAR-USDT | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | NEAR-USDT | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | AAVE-USDT | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | AAVE-USDT | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| okx    | APT-USDT  | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |
| bybit  | APT-USDT  | 2023-01-01T00:00 | 2026-11-27T10:00 |      34234 |    34234 |           0 |         0 |         0 |   100.0000% |             0 | OK    |

Podsumowanie: `{"wiersze": "40/40", "oczekiwane": 1369338, "zapisane": 1369338,
"luki_po_stronie_giełdy": 0, "odrzucone_przez_dq": 0, "brakujące_bez_opisu": 0,
"min_kompletność": 1.0}`.

## Przechodzi do ścieżki produktu (pełna G4)

150 par i 4 giełdy, 72 h ciągłej pracy bez interwencji, Toxiproxy, 500 świec vs ponowne
pobranie, agregaty, kompletność za 30 dni na żywo, test kontraktowy API giełd (cron),
websockety, funding, OI, order book (roadmapa E4, „Dokończenie w ścieżce produktu”).
