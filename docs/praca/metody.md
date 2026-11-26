# Opis zastosowanych metod analizy danych

Rozdział pracy „Metody analizy danych” (mapa: [`README.md`](README.md)). Plik jest
uzupełniany przy domknięciu etapu, który wprowadza metodę: wzór albo algorytm, dane
wejściowe (tylko sprzed `as_of`), parametry, założenia, ograniczenia, sposób sprawdzenia
poprawności (test i bramka) oraz wynik z raportu bramki. Sekcja bez treści ma status ⬜.

## 1. Dane i ich jakość (E4, G4p) ⬜

Źródła (2 giełdy), normalizacja, świece 1 h od 2023-01-01, detektor luk (luki po stronie
giełdy i nasze), reguły Data Quality, cena referencyjna.

## 2. Wskaźniki techniczne i zmienność (E5, G5p) ⬜

`MarketView(as_of)` i zasada point-in-time; cechy `fs-1p`: zwroty logarytmiczne, zmienność
zrealizowana i Parkinsona, ATR, RSI, MACD, ADX, EMA i nachylenie, wstęgi Bollingera,
z-score, Donchian, wolumen względny, korelacja z BTC. Wartości referencyjne liczone
niezależnie.

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
