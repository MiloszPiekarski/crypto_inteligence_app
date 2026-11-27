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

## 2. Wskaźniki techniczne i zmienność (E5, G5p) ⬜

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
źródło zwróci wiersz spoza widoku. Wzory i okna cech: przy domknięciu E5.

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
