# Bramka pracy G4p (E4, ścieżka pracy inżynierskiej): raport

- **Status:** W TOKU (od 26.11.2026). Bramka jest czerwona, dopóki nie ma kaset Bybit
  (nagranie z serwera staging, PR 2 E4) i przebiegu raportu danych na staging.
- **Kryteria (`testy.md`, sekcja 3a, wiersz G4p; ADR-0008):** normalizacja na nagranych
  odpowiedziach: 100% zgodności pól i typów; DQ wykrywa ≥ 95% z 200 wstrzykniętych błędów
  przy fałszywych alarmach < 1%; obsługa 429, przerwania i wznowienia uzupełniania historii
  (testy z atrapami); **staging:** 100% luk wykrytych i opisanych przez detektor (po stronie
  giełdy albo nasza) i kompletność ≥ 99,9% względem świec, które giełda faktycznie
  udostępnia, dla 20 par od 2023-01-01. Wymagania F-04, F-05, F-06 (`work_target`
  w `docs/wymagania.yaml`).
- **Definicja automatu:** [`gates/G4p.yaml`](../../gates/G4p.yaml), uruchomienie
  `make gate G=4p` (lokalnie i w CI, job „8 bramka G4p” poza `ci-ok`, dopóki G4p nie jest
  zaliczona).
- **Zaliczenie (dowód mixed, jak G3):** zielony job „8 bramka G4p (ubuntu-latest)”
  w przebiegu `ci.yml` na `main` **oraz** zielony przebieg `data-report.yml` na `main`
  (blok `evidence` w `gates/G4p.yaml`). Bramka pracy nie przyjmuje dowodu `local`.

## Podział E4 na PR-y (zaakceptowany przez właściciela 26.11.2026)

| PR  | Gałąź                        | Zakres                                                                                                                                                                       | Stan      |
| --- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| 1   | `claude/E4-marketdata-rdzen` | `MarketDataSource`, adaptery OKX i Bybit (ccxt), normalizacja, uniwersum 20 par, DQ, detektor luk, cena referencyjna, `candle.closed` (outbox), punkty kontrolne, testy, G4p | ⏳ ten PR |
| 2   | `claude/E4-ingest-staging`   | sonda dostępu z Amsterdamu (najpierw), kasety Bybit z serwera, proces `ingest` w Compose staging, `data-report.yml`                                                          | ⬜        |
| 3   | `claude/E4-g4p`              | G4p do macierzy `gate`, ten raport z dowodami, dokumentacja etapu                                                                                                            | ⬜        |

## Wybór giełd

Giełda główna **OKX**, druga **Bybit** (propozycja z rozmowy 26.11.2026, zaakceptowana):
obie mają te same pary spot `*/USDT` i historię 1 h przez REST od 2023 (OKX
`/api/v5/market/history-candles`, 100 świec na zapytanie; Bybit `/v5/market/kline`, 1000).
Odrzucone: Kraken (REST OHLC zwraca tylko ostatnie 720 świec, bez historii od 2023),
Coinbase (mało par USDT, cena referencyjna wymaga tej samej pary na obu giełdach).

Dostęp sprawdzony 26.11.2026:

| Skąd                       | OKX                                                                              | Bybit                                                    |
| -------------------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------- |
| sesja asystenta w chmurze  | HTTP 200; 20/20 par spot, pierwsza świeca 1 h każdej pary = 2023-01-01 00:00 UTC | HTTP 403 („CloudFront … block access from your country”) |
| serwer staging (Amsterdam) | ⬜ sonda na początku PR 2                                                        | ⬜ sonda na początku PR 2                                |
| GitHub Actions             | nie dotyczy: CI testuje na kasetach, bez sieci                                   | nie dotyczy                                              |

## Uproszczenia ścieżki pracy i jawne decyzje

- **CoinGecko bez API w czasie działania** (decyzja właściciela 26.11.2026): metadane
  20 par (symbol, nazwa, `coingecko_id`) zapisane raz w
  `services/platform/src/goatcash/marketdata/config/universe.toml`, ze źródłem i datą
  w komentarzu (odczyt CoinGecko `/coins/markets` 26.11.2026). Bez klucza, bez SOPS.
- **Kasety Bybit z serwera w Amsterdamie** (PR 2): Bybit blokuje kraj sesji asystenta,
  więc w PR 1 test normalizacji działa na kasetach OKX, a sprawdzenie „kasety obu giełd”
  (`make marketdata-normalization-test`) jest czerwone do PR 2.
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

## Wyniki (uzupełniane w PR 3)

| Kryterium                                   | Sprawdzenie                  | Wynik |
| ------------------------------------------- | ---------------------------- | ----- |
| Normalizacja 100% (obie giełdy, 20 par)     | `normalization` (CI)         | ⬜    |
| DQ ≥ 95% z 200 błędów, fałszywe alarmy < 1% | `dq-injection` (CI)          | ⬜    |
| 429, przerwanie, wznowienie                 | `resilience` (CI)            | ⬜    |
| Poprawność analityczna (luki, cena ref.)    | `analytics`, `database` (CI) | ⬜    |
| 100% luk opisanych, kompletność ≥ 99,9%     | `data-report.yml` na staging | ⬜    |
