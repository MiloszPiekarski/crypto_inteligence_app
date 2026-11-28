# Opis zastosowanych metod analizy danych

Rozdział pracy „Metody analizy danych” (mapa: [`README.md`](README.md)). Plik jest
uzupełniany przy domknięciu etapu, który wprowadza metodę: wzór albo algorytm, dane
wejściowe (tylko sprzed `as_of`), parametry, założenia, ograniczenia, sposób sprawdzenia
poprawności (test i bramka) oraz wynik z raportu bramki. Sekcja bez treści ma status ⬜.

## 1. Dane i ich jakość (E4, G4p) ✅

Kod: `services/platform/src/goatcash/marketdata/` (`_impl/`), testy:
`services/platform/tests/marketdata/`, bramka: `gates/G4p.yaml`, raport: `docs/gates/G4p.md`.

**Źródła i uniwersum.** Dwie giełdy przez ccxt: OKX (główna) i Bybit (druga), te same pary
spot `*/USDT`. Uniwersum: stała lista 20 par (`config/universe.toml`), świece 1 h od
2023-01-01 00:00 UTC. Dostęp sprawdzony z serwera staging (Amsterdam): obie giełdy 20/20 par,
pierwsza świeca każdej pary 2023-01-01 00:00 UTC.

**Normalizacja.** Symbol `BAZA-KWOTOWANIE`, czas UTC w milisekundach (początek świecy,
wyrównany do godziny), ceny i wolumen jako liczby dziesiętne utworzone z tekstu odpowiedzi
giełdy (bez zamiany na liczby zmiennoprzecinkowe, więc bez błędów zaokrągleń), wolumen
w walucie bazowej, krok ceny i ilości instrumentu. Świeca trafia do danych dopiero po
zamknięciu (OKX: pole `confirm`, obie giełdy: koniec świecy ≤ chwila pobrania).

**Uzupełnianie historii.** Okna po 1000 h; okno = świece obu giełd → kontrola jakości →
cena referencyjna → jeden zapis atomowy razem z punktem kontrolnym (`ingest_checkpoints`).
Przerwanie w środku okna nie zostawia częściowego zapisu, a ponowne uruchomienie zaczyna od
tego samego okna (test właściwości: awaria w dowolnym oknie, wznowienie daje stan identyczny
z przebiegiem bez awarii). Limit zapytań (HTTP 429) i błędy sieci: ponowienia z czekaniem
wykładniczym 1, 2, 4, … s (maks. 60 s, 8 prób).

**Kontrola jakości (Data Quality).** Reguły dla każdej świecy, chronologicznie:

- odrzucenie: cena ≤ 0; niespójne OHLC (nie zachodzi low ≤ open, close ≤ high); wolumen
  < 0; duplikat (ta sama chwila drugi raz);
- oznaczenie: odchylenie od drugiej giełdy |a − b| / ((a + b) / 2) > 3% (oznaczana giełda,
  której cena bardziej odskoczyła od jej własnego poprzedniego zamknięcia); skok ceny
  |r_t| > 8·σ, gdzie r_t = ln(close_t / close_ostatnie_poprawne), σ = odchylenie
  standardowe populacji z ostatnich 168 stóp zwrotu (min. 48; dolna granica 0,01%), bez
  potwierdzenia przez drugą giełdę (zgodność w granicy 3%); po 3 kolejnych skokach na
  spójnym poziomie nowy poziom jest przyjmowany;
- nieaktualność: brak nowej świecy dłużej niż 2 h po zamknięciu ostatniej.

Brak zaglądania w przyszłość: werdykt dla świecy z chwili t zależy tylko od świec z czasem
≤ t (test właściwości: prefiks danych i dowolny podział na partie dają te same werdykty).

**Detektor luk.** Oczekiwane świece = każda pełna godzina od pierwszej świecy udostępnionej
przez giełdę do punktu kontrolnego; luka = ciąg brakujących. Ponowne zapytanie dzieli lukę
na „naszą” (giełda zwraca świecę: uzupełniamy ją przez tę samą kontrolę jakości)
i „po stronie giełdy” (giełda nie udostępnia świecy). Kompletność = zapisane /
(oczekiwane − luki po stronie giełdy).

**Cena referencyjna.** Dla chwili t mediana każdego pola OHLCV ze świec, które przeszły
kontrolę bez oznaczenia (przy dwóch źródłach średnia); jedno poprawne źródło: jego świeca
z adnotacją (`source = single`); brak poprawnego źródła: brak ceny referencyjnej.

**Sprawdzenie poprawności (G4p, CI).** Normalizacja na nagranych odpowiedziach obu giełd
(20 par; oczekiwany wynik liczony niezależnie z surowego JSON): 100% zgodności pól i typów.
200 wstrzykniętych błędów 7 rodzajów: wykrycie 100% (każdy rodzaj ≥ 95%), fałszywe alarmy
0% na danych syntetycznych; prawdziwe dane (5 par × 2000 h od 1.07.2024): 0,11% oznaczeń
przy jednej giełdzie, 0 z 20 000 przy dwóch. Wartości referencyjne (próg 3%, 8·σ,
mediana, kompletność) liczone ręcznie w testach; testy mutacyjne reguł. Wynik na
prawdziwej bazie staging (`data-report.yml` 45981882350, 27.11.2026): 20 par × 2 giełdy,
1 369 338 świec od 2023-01-01, kompletność 100%, 0 luk (giełdy nie mają brakujących świec
1 h w tym okresie), 0 świec odrzuconych, cena referencyjna dla 100% chwil
(`docs/gates/G4p.md`).

**Ograniczenia.** Dwie giełdy (przy dwóch źródłach mediana jest średnią, a odchylenie nie
wskazuje źródła błędu jednoznacznie, stąd porównanie z własną historią); dane co godzinę
przez REST (bez danych bieżących z websocketów); świece zamknięte z opóźnieniem do ok. 2 min
po pełnej godzinie; pełny zakres (150 par, 4 giełdy, 72 h ciągłej pracy) w ścieżce produktu.

## 2. Wskaźniki techniczne i zmienność (E5, G5p) ✅

`MarketView(as_of)` i zasada point-in-time; cechy `fs-1p`: zwroty logarytmiczne, zmienność
zrealizowana i Parkinsona, ATR, RSI, MACD, ADX, EMA i nachylenie, wstęgi Bollingera,
z-score, Donchian, wolumen względny, korelacja z BTC. Wartości referencyjne liczone
niezależnie.

**Zasada point-in-time (`MarketView`, doprecyzowanie z 27.11.2026, karta E5).** Cechy
i agenci widzą dane rynkowe wyłącznie przez `MarketView(as_of, known_at=None)`. Widok
zawsze zwraca tylko świece zamknięte najpóźniej w chwili `as_of` (`ts + 1 h ≤ as_of`;
dla `as_of` wyrównanego do godziny to dokładnie `time < as_of`). Parametr `known_at`
służy do odtwarzania okresu zbieranego na żywo: widok pokazuje wtedy tylko wiersze
zapisane najpóźniej w `known_at` (`ingested_at ≤ known_at`), czyli świecę uzupełnioną
później traktuje jak lukę. Pełne przeliczenie historii działa bez `known_at`, bo historia
od 2023 r. została pobrana w listopadzie 2026 r. i warunek `ingested_at ≤ as_of` dawałby
dla przeszłości pusty widok. Widok sprawdza dane ze źródła drugi raz i zgłasza błąd, gdy
źródło zwróci wiersz spoza widoku.

**Dane wejściowe.** Świece 1 h ceny referencyjnej (`candles_ref`, mediana OKX i Bybit z
sekcji 1). Świeca `ts` jest dostępna od chwili `ts + 1 h`; cechy w chwili `as_of` liczone
są ze świec zamkniętych najpóźniej w `as_of`, a wynik ma `data_cutoff` = zamknięcie
ostatniej użytej świecy. Oznaczenia: c, h, l, v: zamknięcie, szczyt, dołek, wolumen
świecy t; r_t = ln(c_t / c_{t-1}).

**Odcinki, rozgrzewka i braki danych.** Każda para jest dzielona na ciągłe odcinki kolejnych
godzin. Cecha w chwili t zależy tylko od świec swojego odcinka do t włącznie, więc nie
zależy od przyszłości ani od danych sprzed luki. Każda cecha deklaruje okno W (liczbę
świec do pierwszej wartości). Wartość jest liczbą tylko przy statusie `ok`; w pozostałych
przypadkach jest NaN ze statusem: `warmup` (mniej niż W świec od początku danych pary),
`missing_data` (brak świecy w tej godzinie albo mniej niż W świec od luki; bez interpolacji,
także świeca odrzucona przez DQ obu giełd jest luką), `not_applicable` (korelacja BTC
z samym BTC, decyzja właściciela 27.11.2026) i `undefined` (zero w mianowniku: płaska cena
albo zerowy wolumen w oknie; odchylenie standardowe względnie mniejsze niż 1e-12 średniej
traktowane jak zero).

**Cechy `fs-1p` (19; wersja = pierwsze 16 znaków SHA-256 definicji, `66ce07b92a443614`).**
EMA_n: rekurencja y_t = y_{t-1} + α (x_t − y_{t-1}), α = 2 / (n + 1), start od średniej
prostej pierwszych n wartości (jak w TA-Lib). Wygładzanie Wildera: to samo z α = 1 / n.

| Cecha               | Wzór                                                                                          | W   |
| ------------------- | --------------------------------------------------------------------------------------------- | --- |
| `ret_log_1h`        | ln(c_t / c_{t-1})                                                                             | 2   |
| `ret_log_4h`        | ln(c_t / c_{t-4})                                                                             | 5   |
| `ret_log_24h`       | ln(c_t / c_{t-24})                                                                            | 25  |
| `ret_log_168h`      | ln(c_t / c_{t-168})                                                                           | 169 |
| `vol_realized_24h`  | sqrt(Σ r_i², 24 ostatnich godzin)                                                             | 25  |
| `vol_parkinson_24h` | sqrt(Σ ln(h_i / l_i)² / (4 ln 2 · 24)), 24 h                                                  | 24  |
| `atr_14_rel`        | ATR_14 / c_t; TR_t = max(h − l, \|h − c_{t-1}\|, \|l − c_{t-1}\|), ATR = Wilder(TR, 14)       | 15  |
| `rsi_14`            | 100 · G / (G + L), G i L: Wilder(14) zysków i strat godzinowych; brak ruchu: 50               | 15  |
| `macd_rel`          | (EMA_12(c) − EMA_26(c)) / c_t                                                                 | 26  |
| `macd_hist_rel`     | (MACD − EMA_9(MACD)) / c_t                                                                    | 34  |
| `adx_14`            | ADX Wildera (14): +DM, −DM i TR z sumami jak w TA-Lib, DX = 100 · \|DI⁺ − DI⁻\| / (DI⁺ + DI⁻) | 28  |
| `ema_20_dist`       | c_t / EMA_20(c) − 1                                                                           | 20  |
| `ema_50_slope_24h`  | EMA_50(c)_t / EMA_50(c)_{t-24} − 1                                                            | 74  |
| `bb_pctb_20`        | (c − (m − 2σ)) / (4σ), m i σ: średnia i odchylenie (populacyjne) c z 20 h                     | 20  |
| `bb_width_20`       | 4σ / m (20 h)                                                                                 | 20  |
| `zscore_close_168h` | (c − m) / σ (168 h)                                                                           | 168 |
| `donchian_pos_168h` | (c − min l) / (max h − min l), 168 h                                                          | 168 |
| `volume_rel_168h`   | v_t / średnia v z 168 h                                                                       | 168 |
| `corr_btc_168h`     | współczynnik Pearsona r pary i r BTC z 168 h (oba szeregi bez luk w oknie)                    | 169 |

**Implementacja.** Polars (wektorowo, osobno dla każdego odcinka); jedna funkcja liczy
pełne przeliczenie historii i cechy w chwili `as_of` (na żywo po `candle.closed`), więc obie
drogi dają te same liczby. Zapis w `feature_values` (klucz: zbiór cech, para aktywów, cecha,
`as_of`; migracja 0004) z wykryciem zmiany bit w bit; zdarzenie `features.ready` v2 tylko
przy zmianie (`docs/gates/G5p.md`).

**Weryfikacja (G5p, `docs/gates/G5p.md`).** Brak zaglądania w przyszłość: dla 1000 losowych
chwil (także w środku godziny) cechy z danych obciętych do t są bit w bit równe cechom
z pełnego przeliczenia, dla wszystkich 19 cech; do tego replay z `known_at`, niezmienność
wyniku przy zmianie danych z przyszłości i testy mutacyjne (przesunięcie w złą stronę,
normalizacja całą serią, okno wycentrowane: wykryte). Wartości referencyjne liczone
niezależnie dwiema implementacjami: TA-Lib (C) i czystym Pythonem, na danych syntetycznych
i prawdziwej cenie z kaset E4 (5 par × 2000 h): |różnica| ≤ 1e-9 · max(1, |wzorzec|), cecha
ma wartość dokładnie tam, gdzie wzorzec (największa zaobserwowana różnica ok. 2e-12, %B
przez sumy kwadratów w TA-Lib); do tego przykłady policzone ręcznie. Dwa pełne przeliczenia
historii (także w osobnym procesie z jednym wątkiem Polars i po zapisie do Postgresa) dają
ten sam skrót SHA-256 bitów wartości.

**Ograniczenia.** Jedno odejście od TA-Lib: RSI przy płaskiej cenie = 50 (TA-Lib: 0).
Cechy rekurencyjne zależą od początku odcinka (po luce startują od nowa), a pełne
przeliczenie czyta całą historię pary (20 par × ok. 34 tys. godzin; dla 150 par potrzebny
stan przyrostowy: produkt). Cechy z danych pełnego E4 (funding, OI, order book, dominacja
BTC, Fear & Greed, TVL), eksport Parquet, test live vs replay przez 7 dni i wydajność
150 par: ścieżka produktu. Liczenie na staging (worker) od E7 (decyzja 27.11.2026).

## 3. Agenci analityczni (E7, G7p) ⬜

- Trend: EMA i ADX, kalibrowana regresja logistyczna → `p_up`.
- Ryzyko i zmienność: GARCH(1,1), EWMA, kwantyle zwrotu, VaR 95%, CVaR.
- Reżim rynku: ukryty model Markowa (HMM) z 4–5 stanami, filtr online.
- Historyczny: k najbliższych sąsiadów (analogie w przestrzeni cech, tylko sytuacje
  zakończone przed `as_of`).
- Punkty odniesienia: `baseline_50`, `baseline_freq`.

## 4. Rozliczanie prognoz: Forecast Ledger (E7, G7p) ⬜

Zapis prognozy przed faktem (hash), Evaluator, metryki: Brier, log-loss, pinball, pokrycie
przedziałów, ECE (kalibracja), wyniki per agent × reżim × horyzont.

## 5. Model uczenia maszynowego (E8, G8p) ⬜

LightGBM: kierunek (z kalibracją izotoniczną) i kwantyle q10/q50/q90 (z korektą conformal),
horyzont 24 h; walidacja walk-forward z purgingiem i embargo, zbiór zamknięty; test
cechy-pułapki; raport względem punktów odniesienia.

## 6. Fuzja ocen, ocena ryzyka i podpowiedzi (E9, G9p) ⬜

Regresja logistyczna na prognozach agentów (walk-forward) z regułą awaryjną; niezgoda
agentów (entropia, rozrzut); reguły oceny ryzyka; szablony komunikatów i podpowiedzi
(bez porady inwestycyjnej).

## 7. Testowanie strategii (E11, G11p) ⬜

Silnik zdarzeniowy (decyzja na zamknięciu, wykonanie na otwarciu następnej świecy,
konserwatywna kolejność SL/TP), model kosztów, metryki: zwrot, CAGR, Sharpe, Sortino,
maksymalne obsunięcie, trafność, profit factor.
