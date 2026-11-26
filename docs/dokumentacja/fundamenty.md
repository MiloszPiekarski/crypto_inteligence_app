# Roadmapa i dokumentacja techniczna platformy

Nov 8, 2026 · @Miłosz

Dokument jest źródłem prawdy dla budowy platformy od zera: zakładka **Fundamenty i decyzje** ustala stos i dostawców, **Roadmapa E0–E17** opisuje każdy etap według 12 pól, a **Testy i quality gates** określa, kiedy wolno przejść dalej. Zmiana którejkolwiek decyzji wymaga wpisu ADR (Architecture Decision Record) i aktualizacji tego dokumentu.

## 0. Zakres pracy inżynierskiej

Od 26.11.2026 projekt ma dwie ścieżki realizacji (ADR-0008): **ścieżkę pracy** (bieżąca,
minimum spełniające zakres pracy inżynierskiej) i **ścieżkę produktu** (po obronie, pełna
roadmapa). Nic z pełnego zakresu nie znika: każdy etap ścieżki pracy ma w roadmapie
podsekcję „Dokończenie w ścieżce produktu”, a etapy odłożone w całości mają status
„⏸ odłożone (produkt)”.

### 0.1. Temat

- **PL:** Aplikacja webowa do analizy rynku kryptowalut z wykorzystaniem systemu wieloagentowego
- **EN:** A web application for cryptocurrency market analysis using a multi-agent system

### 0.2. Zakres pracy (dosłownie)

> Celem projektu jest opracowanie aplikacji webowej umożliwiającej analizę wybranych danych
> dotyczących rynku kryptowalut z wykorzystaniem systemu wieloagentowego. Aplikacja powinna
> wspierać użytkownika w analizie danych rynkowych, takich jak ceny, wolumen obrotu,
> zmienność oraz wybrane wskaźniki analizy technicznej. System powinien składać się
> z kilku wyspecjalizowanych modułów lub agentów odpowiedzialnych za różne aspekty analizy,
> na przykład analizę trendów, ocenę ryzyka, analizę historycznych danych rynkowych oraz
> prezentowanie syntetycznych podpowiedzi użytkownikowi. W ramach pracy należy wykorzystać
> wybrane metody sztucznej inteligencji lub uczenia maszynowego do analizy danych
> historycznych oraz generowania pomocniczych ocen dotyczących możliwych scenariuszy
> rynkowych. System nie powinien podejmować decyzji inwestycyjnych za użytkownika, lecz
> prezentować wyniki analizy w formie informacyjnej, na przykład jako zestaw wskaźników,
> ocen ryzyka, wykresów oraz komunikatów ostrzegawczych. Aplikacja może również zawierać
> moduł testowania strategii na danych historycznych, umożliwiający ocenę skuteczności
> przyjętych założeń z wykorzystaniem wybranych metryk. Dodatkowo należy przedstawić model
> danych, architekturę aplikacji wraz z wymaganiami funkcjonalnymi i niefunkcjonalnymi,
> opis zastosowanych metod analizy danych oraz projekt graficznego interfejsu użytkownika.
> Następnie należy zaimplementować i przetestować prototyp aplikacji, uwzględniając
> poprawność działania modułów analitycznych oraz sposób prezentacji wyników użytkownikowi.

### 0.3. Wymóg z zakresu pracy → etap → artefakt i dowód

Tabela do pisania pracy: gdzie w repo jest dowód realizacji każdego wymogu. Mapa
„rozdział pracy → dokumenty”: [`docs/praca/README.md`](../praca/README.md).

| Wymóg z zakresu pracy                                                    | Etap (bramka)         | Artefakt w repo                                                                                      | Dowód                                                           |
| ------------------------------------------------------------------------ | --------------------- | ---------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Aplikacja webowa                                                         | E6 (G6p), E12b (G12p) | `services/platform` (`api`), `apps/web`; wdrożenie `app.goatcash.app` i `api.goatcash.app`           | Schemathesis w G6p; Playwright E2E w G12p; test dymny wdrożenia |
| Dane: ceny, wolumen obrotu                                               | E4 (G4p)              | moduł `marketdata`: 2 giełdy, 20 par, świece 1 h od 01.2023, DQ, cena referencyjna                   | G4p: DQ ≥ 95%, raport luk i kompletności ze staging             |
| Zmienność i wskaźniki analizy technicznej                                | E5 (G5p)              | moduł `features` (`fs-1p`, `MarketView(as_of)`)                                                      | G5p: point-in-time 100%, wartości referencyjne < 1e-9           |
| Kilka wyspecjalizowanych agentów (trend, ryzyko, analiza historyczna)    | E7 (G7p)              | moduł `agents`: Trend, Ryzyko i zmienność, Reżim, Historyczny; kontrakt `Evidence` v1                | G7p: testy właściwości agentów, point-in-time agentów           |
| Prezentowanie syntetycznych podpowiedzi                                  | E9 (G9p), E12b (G12p) | moduł `fusion`: ocena łączna, ocena ryzyka, ostrzeżenia, podpowiedzi z szablonów                     | G9p: tabela reguł ryzyka, test słownika szablonów               |
| Metody AI/ML na danych historycznych, oceny scenariuszy                  | E7 (G7p), E8 (G8p)    | HMM (reżim), regresja logistyczna (kalibracja), kNN (analogie), LightGBM kierunek i kwantyle 24 h    | G8p: walk-forward, brak wycieku, odtwarzalność, raport          |
| Rozliczanie jakości ocen (uczciwość wyników)                             | E7 (G7p)              | moduł `ledger`: Forecast Ledger, Brier, log-loss, pinball, pokrycie, ECE                             | G7p: Ledger = ręczne przeliczenie 200 prognoz (1e-12)           |
| Brak decyzji inwestycyjnych, forma informacyjna, komunikaty ostrzegawcze | E9 (G9p), E12b (G12p) | szablony bez trybu rozkazującego; informacja „to nie jest porada inwestycyjna” na każdym widoku      | G9p: test słownika; G12p: test informacji na każdym widoku      |
| Moduł testowania strategii z metrykami (opcjonalny)                      | E11 (G11p)            | moduł `backtest`: 3 strategie referencyjne, zwrot, CAGR, Sharpe, Sortino, maks. obsunięcie, trafność | G11p: zgodność z ręcznym przeliczeniem, strategia-pułapka       |
| Model danych                                                             | E2 (G2)               | roadmapa E2 „Model danych”, ADR-0002, migracje Alembic                                               | G2: migracja w obie strony                                      |
| Architektura aplikacji                                                   | E2 (G2), E3 (G3)      | sekcja 2 tego dokumentu, `docs/architektura/c4.md`, `stride.md`, ADR-0001…0008                       | G2, G3                                                          |
| Wymagania funkcjonalne i niefunkcjonalne                                 | E2 (G2)               | `docs/wymagania.yaml` (pole `track`: praca albo produkt)                                             | G2: `make requirements-check`                                   |
| Opis zastosowanych metod analizy danych                                  | E5, E7, E8, E9, E11   | `docs/praca/metody.md` (uzupełniany przy domknięciu każdego z tych etapów)                           | raporty bramek pracy                                            |
| Projekt graficznego interfejsu użytkownika                               | E12a (część G12p)     | persony, 4 zadania kluczowe, makiety w Figma Free (eksport w `docs/praca/gui/`), mini design system  | pliki w repo                                                    |
| Implementacja i testy prototypu: poprawność modułów analitycznych        | E4–E11 (bramki pracy) | testy z wartościami referencyjnymi, testy właściwości, testy point-in-time                           | `docs/gates/G<nr>p.md`, `G<nr>p.passed.json`                    |
| Testy sposobu prezentacji wyników użytkownikowi                          | E12b (G12p)           | Vitest, Playwright, axe, test z 3 osobami i kwestionariusz SUS                                       | G12p, raport `docs/praca/test-uzytkownikow.md`                  |

### 0.4. Etapy: ścieżka pracy i ścieżka produktu

Kolejność prac i minimum każdego etapu: tabela „Kolejność prac” na początku
[`roadmapa.md`](roadmapa.md); kryteria bramek pracy: [`testy.md`](testy.md), sekcja 3a.

| Etap       | Ścieżka              | W ścieżce pracy                                                | Bramka |
| ---------- | -------------------- | -------------------------------------------------------------- | ------ |
| E0–E3      | praca (pełny zakres) | zaliczone; z E0 do produktu przechodzi tylko Resend            | G0–G3  |
| E4         | praca (okrojony)     | 2 giełdy, 20 par, świece 1 h od 01.2023, DQ, cena referencyjna | G4p    |
| E5         | praca (okrojony)     | ok. 15–20 cech, `MarketView(as_of)`, point-in-time             | G5p    |
| E6         | praca (okrojony)     | API tylko do odczytu, bez kont użytkowników                    | G6p    |
| E7         | praca (okrojony)     | 4 agentów, 2 punkty odniesienia, Forecast Ledger               | G7p    |
| E8         | praca (okrojony)     | LightGBM kierunek + kwantyle 24 h, walk-forward, bez MLOps     | G8p    |
| E9         | praca (okrojony)     | fuzja, ocena ryzyka, ostrzeżenia, podpowiedzi z szablonów      | G9p    |
| E10, E10a  | produkt (⏸ odłożone) | brak                                                           | –      |
| E11        | praca (okrojony)     | silnik backtestu, 3 strategie referencyjne, metryki            | G11p   |
| E11a       | produkt (⏸ odłożone) | brak                                                           | –      |
| E12a, E12b | praca (okrojony)     | makiety w Figma Free + panel wyników, test z 3 osobami         | G12p   |
| E13–E18    | produkt (⏸ odłożone) | brak                                                           | –      |

## 1. Decyzje w skrócie

Wybrany układ: **Python (FastAPI) + PostgreSQL/TimescaleDB + Redis na jednej maszynie Oracle Always Free na czas budowy, Next.js na Cloudflare, modele ML własne, LLM przez bramkę z kilkoma dostawcami**. Całość w kontenerach, żeby przeniesienie na płatny serwer w UE przy publicznym starcie było zmianą konfiguracji, nie przepisaniem.

| Obszar                  | Decyzja                                                                                                                         | Dlaczego                                                                   |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Architektura            | Modularny monolit + workery + odizolowany executor bota                                                                         | Jedna osoba utrzymuje; granice modułów pozwalają później wydzielić serwisy |
| Repozytorium            | Publiczny monorepo na GitHub (pnpm + uv)                                                                                        | Jeden PR zmienia kontrakt, backend i frontend naraz                        |
| Backend                 | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic                                                                        | Ekosystem ML i danych; typy współdzielone z kontraktem OpenAPI             |
| Zadania w tle           | arq (Redis) + harmonogram cron arq                                                                                              | Natywnie asynchroniczne, lekkie, bez Celery i Ray                          |
| Baza                    | PostgreSQL 17 + TimescaleDB + pgvector                                                                                          | Szeregi czasowe, dane relacyjne i wektory w jednym silniku                 |
| Cache, strumienie       | Valkey (otwarty fork Redis)                                                                                                     | Kolejki, pub/sub, Redis Streams dla tablicy dowodów                        |
| Archiwum i kopie        | Cloudflare R2 (Parquet, kopie bazy, artefakty modeli)                                                                           | Brak opłat za transfer wychodzący                                          |
| Frontend                | Next.js (App Router), TypeScript, Tailwind, shadcn/ui, TanStack Query, Lightweight Charts, ECharts                              | SSR dla publicznych stron aktywów (SEO), dojrzały ekosystem                |
| Hosting frontu          | Cloudflare (Workers przez adapter OpenNext) + CDN + WAF                                                                         | Darmowy plan pozwala na użytek komercyjny; ochrona DDoS                    |
| Hosting backendu        | Faza budowy: Oracle Always Free (ARM 2 OCPU / 12 GB). Publiczny start: płatny VPS w UE                                          | Patrz sekcja 4                                                             |
| Uwierzytelnianie        | Better Auth (w Next.js, dane w naszym Postgresie) + JWT weryfikowany w FastAPI przez JWKS                                       | Brak uzależnienia od dostawcy, 2FA i passkeys                              |
| Dane rynkowe            | Publiczne API giełd przez ccxt (OKX, Bybit, Coinbase, Kraken) + CoinGecko + DefiLlama                                           | Patrz sekcja 3                                                             |
| Giełdy dla bota         | Najpierw OKX i Bybit (najlepsze środowiska testowe), potem Kraken i Coinbase                                                    | Patrz sekcja 3                                                             |
| ML                      | LightGBM, scikit-learn, statsmodels, arch, hmmlearn, Polars, DuckDB, Optuna, MLflow                                             | Modele tablicowe, interpretowalne, trening na CPU                          |
| LLM                     | Bramka LiteLLM; Claude Haiku 5.5 do narracji, Claude Sonnet 5.5 do analiz pogłębionych, Gemini Flash-Lite i DeepSeek jako zapas | Patrz sekcja 5                                                             |
| Obserwowalność          | OpenTelemetry → Grafana Cloud (darmowy plan), Sentry, Langfuse dla LLM, zewnętrzny monitoring dostępności                       | Wiemy, który agent, model lub źródło przestało działać                     |
| Sekrety                 | SOPS + age (zaszyfrowane pliki w repo), GitHub Environments, gitleaks, push protection                                          | Bezpieczne w publicznym repo, bez dostawcy                                 |
| CI/CD                   | GitHub Actions → obrazy w GHCR → wdrożenie Docker Compose przez SSH z zatwierdzeniem                                            | Darmowe dla repo publicznego, proste do odtworzenia                        |
| Infrastruktura jako kod | Terraform (Oracle, Cloudflare) + Ansible do konfiguracji serwera                                                                | Każde środowisko odtwarzalne jedną komendą                                 |
| UI design               | Figma (system projektowy) + Lovable tylko do klikalnych prototypów                                                              | Patrz sekcja 7                                                             |

### Zasady nadrzędne

1. **Analizy per aktyw, nie per użytkownik.** Koszt obliczeń i LLM rośnie z liczbą par, nie użytkowników.
2. **Jedna ścieżka kodu dla live i backtestu.** Agenci nie wiedzą, czy działają na historii.
3. **Żadnych cichych fallbacków.** Brak danych to stan jawny, widoczny w UI.
4. **Każdy dostawca za adapterem.** Źródło danych, model LLM czy giełdę można wymienić bez zmian w logice.
5. **Etap kończy się bramką jakości.** Bez zielonej bramki nie zaczynamy kolejnego etapu zależnego.

## 1a. Samouczenie: kontrolowana pętla uczenia

Platforma jest **samouczącym się systemem tradingowym**: uczy się z rozliczonych wyników własnych prognoz, backtestów i paper tradingu, a na prawdziwe pieniądze trafia tylko to, co przeszło bramkę jakości. Plan od początku miał trzy poziomy uczenia: wagi agentów, retrening modeli i kalibrację. Nie zamykał jednak pętli na samych decyzjach tradingowych. Uzupełnia to nowy etap **E11a**.

### Poziomy uczenia

| Poziom                          | Czego system się uczy                                 | Z jakich danych                                              | Metoda                                                                            | Częstotliwość         | Etap       |
| ------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------- | --------------------- | ---------- |
| L1. Zaufanie do agentów         | Ile waży głos każdego agenta w danym reżimie          | Rozliczone prognozy w Forecast Ledger                        | Wagi multiplikatywne (Hedge)                                                      | Po każdym rozliczeniu | E9         |
| L2. Modele prognoz              | Kierunek i zakres zwrotu                              | Cechy i etykiety z historii                                  | LightGBM, retrening + champion/challenger                                         | Co tydzień            | E8         |
| L3. Kalibracja                  | Czy "60%" naprawdę sprawdza się w 60% przypadków      | Forecast Ledger                                              | Kalibracja izotoniczna                                                            | Co tydzień            | E9         |
| L4. Filtr decyzji (nowe)        | Które sygnały warto zamienić na transakcję i jak dużą | Wyniki transakcji z backtestów walk-forward i paper tradingu | Meta-labeling: klasyfikator LightGBM "czy transakcja będzie zyskowna po kosztach" | Co tydzień            | E11a       |
| L5. Dobór strategii (nowe)      | Która strategia z portfela działa w obecnym reżimie   | Wyniki paper tradingu per strategia i reżim                  | Kontekstowy bandyta (Thompson sampling)                                           | Codziennie            | E11a, E14a |
| L6. Strojenie parametrów (nowe) | Progi wejścia, odległość SL/TP, horyzont              | Backtest walk-forward                                        | Optuna z karą za przeuczenie (Deflated Sharpe Ratio)                              | Co miesiąc            | E11a       |
| L7. Uczenie ze wzmocnieniem     | Cała polityka decyzji naraz                           | Symulator rynku z kosztami                                   | PPO lub podobne                                                                   | Badania               | E17        |

### Granice uczenia, których system nie może przekroczyć

1. **Limity ryzyka, reguły Risk Governora i kill switch są poza zasięgiem uczenia.** Moduł `learning` nie ma do nich uprawnień zapisu (sprawdza to import-linter i uprawnienia bazy). Zmienia je tylko człowiek, przez PR i ADR.
2. **Każda nowa wersja polityki najpierw działa 14 dni w trybie cienia.** Promocja następuje tylko przy statystycznie istotnej poprawie.
3. **Uczenie wyłącznie na danych rozliczonych:** z backtestu, paper tradingu i Ledgera. Nigdy w trakcie sesji na żywych zleceniach, więc system nie może na przykład "odgrywać się" po stratach większymi pozycjami.
4. **Zmiany są ograniczone:** parametry zmieniają się maksymalnie o ±20% na cykl, a wielkość pozycji nigdy nie przekracza ćwiartki ułamka Kelly'ego ani limitów użytkownika.
5. **Automatyczny powrót:** jeśli aktywna polityka przez 7 dni wypada gorzej niż punkt odniesienia, system wraca do poprzedniej wersji i wysyła alert.
6. **Jawność:** publiczna strona "Jak system się uczy" pokazuje historię wersji, co się zmieniło i wynik przed oraz po zmianie. To nasza przewaga nad projektami, które tylko deklarują "self-learning".

W pracy inżynierskiej opisujemy poziomy L1–L3. Poziomy L4–L6 należą do produktu, bo w pracy bot działa tylko w trybie informacyjnym.

## 1b. Wywiad zdarzeniowy: wydarzenia ze świata jako sygnały long i short

Platforma obserwuje wydarzenia, które mogą poruszyć rynkiem kryptowalut, i zamienia je w rozliczalne oceny: których aktywów to dotyczy, w którą stronę i jak mocno rynek zwykle reaguje oraz ile z tej reakcji już się dokonało. Szczegółowa karta etapu to **E10a** w zakładce Roadmapa. Ta sekcja opisuje zasadę i elementy, które wyróżniają rozwiązanie.

**Gdzie jest przewaga, a gdzie jej nie ma.** Gdy news o nagłym wydarzeniu dotyczy dużej spółki, pierwszy ruch ceny wykonują w sekundach algorytmy wysokiej częstotliwości. Kto czyta wiadomość po spadku o 15%, nie zarobi już na tym ruchu. Zarobić można na tym, co dzieje się później: kontynuacji spadku, przesadnej reakcji i odbiciu albo **efekcie przeniesienia na powiązane aktywa**. Przykład: szok w spółce z sektora AI może w kolejnych godzinach przenieść się na tokeny AI, które reagują wolniej i mocniej.

### Pięć rozwiązań, które wyróżniają moduł

1. **Badanie zdarzeń zamiast zgadywania przez model językowy.** LLM tylko rozpoznaje i opisuje zdarzenie. Kierunek i siłę reakcji wyznacza historia: jak rynek reagował na podobne zdarzenia (mediana, rozrzut, odsetek spadków, liczba przypadków), po oddzieleniu ruchu całego rynku.
2. **Wskaźnik "ile już w cenie".** Ruch, który się dokonał, jest porównywany z typową reakcją. Jeśli cena spadła już bardziej niż zwykle, sygnałem może być odbicie, a nie short.
3. **Wiarygodność źródeł liczona, nie zakładana.** Każde źródło ma własną historię trafności w Ledgerze: jak często jego informacje się potwierdzały i jak szybko. Nowe źródło startuje z niską wiarygodnością i zyskuje ją z czasem (model beta-dwumianowy).
4. **Potwierdzenie reakcji na łańcuchu.** Jeśli po zdarzeniu rośnie napływ danego tokena na giełdy albo duże portfele zaczynają sprzedawać, ocena siły zdarzenia rośnie. Brak takich ruchów obniża jej pewność.
5. **Rynki prognoz jako czujnik oczekiwań.** Zmiany szans na rynkach prognoz (np. decyzja w sprawie ETF, wynik wyborów, decyzja banku centralnego) pokazują, jak tłum ocenia prawdopodobieństwo zdarzenia, zanim ono nastąpi. Publiczne dane rynkowe Polymarket są dostępne bez klucza, uwierzytelniania i portfela ([Polymarket docs](https://docs.polymarket.com/market-data/overview.md)). Tylko je czytamy; nie handlujemy tam, bo w Polsce otwieranie pozycji jest zablokowane.

### Long, short i brak transakcji

Karta zdarzenia kończy się jedną z trzech ocen z prawdopodobieństwem: **scenariusz wzrostowy**, **scenariusz spadkowy** albo **brak przewagi**, zawsze z warunkiem unieważnienia. Na rynku spot sygnał spadkowy oznacza "sprzedaj lub nie kupuj". Prawdziwy short wymaga kontraktów perpetual, które bot obsłuży dopiero po GA, z twardym limitem dźwigni.

### Zasady dotyczące osób i plotek

- Zdarzenia dotyczące **konkretnych osób** (prezes, założyciel, polityk) są opisywane wyłącznie jako kategoria, np. "kryzys reputacyjny kierownictwa spółki X". Każdy fakt ma odnośnik do źródła. Platforma nie powtarza zarzutów ani szczegółów życia prywatnego.
- Zdarzenie dotyczące osoby pojawia się u użytkowników dopiero po potwierdzeniu w co najmniej dwóch wiarygodnych źródłach. Wcześniej wpływa tylko na ostrożność Risk Governora.
- Platforma niczego nie publikuje w mediach społecznościowych z wyprzedzeniem wobec użytkowników i nie tworzy własnych treści o zdarzeniach poza kartą z źródłami. To ogranicza ryzyko wzmacniania plotek i manipulacji rynkiem.

### Studium przypadku: Nvidia, 8–12 listopada 2026

Zarząd Nvidii ogłosił w niedzielę dochodzenie w sprawie relacji prezesa z menedżerką, którą wywiad USA uznał za chińską agentkę. Rynek nie zareagował na samą obyczajowość, tylko na skutki dla biznesu: ryzyko utraty kluczowej osoby, kontrolę eksportu do Chin i ład korporacyjny. Przebieg:

| Moment                    | Co się stało                                              | Reakcja ceny                                                                                                                     |
| ------------------------- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Nd 8.11, giełdy zamknięte | Ogłoszenie dochodzenia                                    | Perpetuale NVDA na Hyperliquid −3,8% (do 180,15 USD, ok. 200 mln USD obrotu), zanim ruszył jakikolwiek handel akcjami; ETH −4,2% |
| Pn 9.11                   | Pierwsza sesja                                            | Akcje −4,3%                                                                                                                      |
| Wt 10.11                  | Rosną naciski polityczne                                  | Akcje −5,5%                                                                                                                      |
| Śr 11.11 po sesji         | Doniesienia o drugim romansie i o przygotowaniu odwołania | −8% po sesji; Polymarket: 89% na odejście prezesa do końca roku                                                                  |
| Czw 12.11 przed sesją     | Zarząd decyduje; CNN donosi o rezygnacji                  | −7,6% do −10%; konkurenci AMD i Broadcom na plusie                                                                               |

Łącznie wartość spółki spadła w tydzień o 450–600 mld USD (CBS, Ara). Trzy wnioski dla agenta:

1. **Pierwsza reakcja była mała, pełny ruch trwał cały tydzień.** W pierwszych godzinach spadek wyniósł ok. 4%, a do czwartku sięgnął kilkunastu procent. To potwierdza założenie, że nasza przewaga leży w skali godzin i dni, a nie sekund.
2. **Zdarzenie to historia z kolejnymi etapami, a nie pojedynczy news.** Dochodzenie, przyznanie się, drugi romans, odwołanie: każdy etap przesuwał cenę od nowa. Rynki prognoz od razu wyceniały kolejny etap (kontrakty na odejście prezesa na Kalshi i Polymarket).
3. **Rynek krypto wycenił akcję pierwszy.** Gdy giełdy akcji były zamknięte, perpetuale na akcje i akcje tokenizowane były jedynym miejscem odkrywania ceny. NVDA jest dziś największym rynkiem akcyjnym na Hyperliquid i czwartym na całej platformie (po BTC, ETH i HYPE).

Z tego wynikają trzy nowe mechanizmy agenta:

- **Drzewo eskalacji.** Karta zdarzenia ma listę możliwych kolejnych etapów (np. dochodzenie → odwołanie → śledztwo regulatora) z prawdopodobieństwami, które aktualizują się z newsów i rynków prognoz. Sygnał dotyczy też ruchu przy następnym etapie, nie tylko przy obecnym. Agent zapisuje, jak takie historie rozwijały się wcześniej, i na tej podstawie ocenia, ile ruchu jeszcze zostało.
- **Tryb weekendowy (most TradFi–krypto).** Gdy giełdy tradycyjne są zamknięte, agent śledzi lukę między ceną perpetuali na akcje oraz akcji tokenizowanych a piątkowym zamknięciem. Z luki, obrotu i stopy finansowania wyznacza oczekiwany kierunek poniedziałkowego otwarcia i wpływ na kryptowaluty powiązane narracyjnie.
- **Klasa „ryzyko kluczowej osoby” i mapa zarażenia sektora.** Graf powiązań zawiera, od kogo zależy dana spółka lub protokół, oraz kto zyskuje na jego problemach. W przypadku Nvidii: konkurenci (AMD, Broadcom) rosną, a tokeny z narracją AI (np. TAO, RENDER, FET) i ETH są narażone na spadki.

Handel perpetualami na akcje wymaga osobnej analizy prawnej (odłożonej zgodnie z założeniami). Do tego czasu tryb weekendowy jest tylko sygnałem w aplikacji, bez wykonania przez bota.

Moduł nie wchodzi do pracy inżynierskiej, bo jej zakres nie obejmuje analizy newsów.

## 2. Architektura docelowa

System składa się z sześciu procesów uruchamianych z dwóch obrazów Dockera (Python i Next.js) oraz jednego osobnego obrazu executora bota. Wszystkie komunikują się przez Postgres, Valkey (strumienie i kolejki) i wewnętrzne HTTP; tylko frontend i API są wystawione do internetu, przez Cloudflare.

&#91;embedded content: architektura · faza budowy na Oracle Always Free\]

Ruch użytkownika wchodzi tylko przez Cloudflare; baza i Valkey nie są widoczne z internetu, a executor łączy się z bazą przez prywatną sieć Tailscale.

### Procesy

| Proces          | Odpowiedzialność                                                              | Skalowanie                               |
| --------------- | ----------------------------------------------------------------------------- | ---------------------------------------- |
| `web` (Next.js) | Interfejs, SSR stron publicznych, logowanie (Better Auth), proxy do API       | Bezstanowy, Cloudflare Workers           |
| `api` (FastAPI) | REST + WebSocket/SSE, autoryzacja JWT, limity zapytań, odczyt wyników         | Bezstanowy, 1–N replik                   |
| `ingest`        | Websockety giełd, zapis świec/transakcji/funding/OI, uzupełnianie luk         | 1 proces na grupę giełd                  |
| `worker`        | Zadania arq: cechy, agenci, fuzja, narracje LLM, alerty, backtesty            | N procesów, kolejki z priorytetami       |
| `scheduler`     | Cron arq: harmonogram analiz (15 min / 1 h / 4 h / 1 d), retrening, ewaluacja | Dokładnie 1 instancja (blokada w Valkey) |
| `executor`      | Klucze API użytkowników, zlecenia, uzgadnianie stanu, kill switch             | Osobna maszyna, osobna sieć, stałe IP    |

### Moduły w kodzie Pythona (pakiet `goatcash` w katalogu `services/platform`)

- `marketdata` – adaptery giełd i dostawców, normalizacja, kontrola jakości
- `features` – biblioteka cech point-in-time, wspólna dla live i backtestu
- `agents` – agenci, kontrakt `Evidence`, rejestr agentów
- `fusion` – łączenie dowodów, kalibracja, Risk Governor
- `ledger` – Forecast Ledger, rozliczanie prognoz, metryki
- `ml` – trening, rejestr modeli, inferencja
- `llm` – bramka modeli, prompty jako pliki wersjonowane, walidatory, ewaluacja
- `backtest` – silnik zdarzeniowy, koszty, raporty
- `alerts` – reguły, kanały dostarczania
- `users` – profile, preferencje, uprawnienia, limity
- `bot_core` – polityki, intencje zleceń, silnik ryzyka przed transakcją (współdzielony przez worker i executor)
- `common` – konfiguracja, logowanie, telemetria, błędy

Moduły komunikują się tylko przez publiczne interfejsy (`goatcash.<moduł>.api`); implementacja leży w `goatcash.<moduł>._impl`. Reguła jest sprawdzana w CI narzędziem import-linter. _Decyzja z E1 (22.11.2026, ADR-0001): pakiet nazywa się `goatcash`, a nie `platform`, bo `platform` przesłania moduł standardowy Pythona o tej nazwie._

### Główne przepływy danych

1. **Dane rynkowe:** giełda → `ingest` (websocket) → walidacja → TimescaleDB (`candles`, `trades_agg`, `funding`, `open_interest`) → zdarzenie `candle.closed` w Valkey Streams.
2. **Analiza:** `candle.closed` → `worker` liczy cechy → agenci publikują `Evidence` (tabela + strumień) → fuzja i Risk Governor → `assessment` → Narrator LLM → `narrative` → cache → `api` → `web`.
3. **Rozliczanie:** po upływie horyzontu `scheduler` uruchamia Evaluator → wynik prognozy w `forecast_outcomes` → aktualizacja wag fuzji i metryk.
4. **Newsy:** RSS i API → deduplikacja → klasyfikator lokalny → LLM tylko dla niejednoznacznych i do ekstrakcji zdarzeń → `news_events` → Sentiment Agent.
5. **Bot:** `assessment` + polityka użytkownika → `order_intent` w Postgresie → `executor` pobiera intencję, weryfikuje ponownie ryzyko, wysyła zlecenie → `orders`, `fills`, `positions` → powiadomienie.
6. **Archiwum:** dane starsze niż 90 dni kompresowane w Timescale, kopie miesięczne w Parquet na R2 do treningów i badań w DuckDB.

## 3. Dane rynkowe i giełdy

Najszersze pokrycie przy zerowym koszcie daje **bezpośrednie pobieranie danych z kilku dużych giełd przez ich publiczne API**, uzupełnione o agregator metadanych (CoinGecko). Płatni agregatorzy tickowi są potrzebni dopiero do badań mikrostruktury, a ich ceny zaczynają się od kilkuset dolarów miesięcznie.

### Dostawcy danych analitycznych

| Dostawca                                                       | Co daje                                                                                 | Darmowy dostęp                                                                                                                                                                                                                               | Rola u nas                                                       | Decyzja                                       |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | --------------------------------------------- |
| OKX, Bybit, Coinbase, Kraken (publiczne API przez ccxt)        | Świece, transakcje, order book, funding, open interest w czasie rzeczywistym i historii | Bezpłatne; limity zapytań per IP                                                                                                                                                                                                             | Główne źródło surowych danych; cena referencyjna = mediana giełd | **Tak, od E4**                                |
| CoinGecko API                                                  | Kapitalizacja, podaż, kategorie, metadane, DEX                                          | Demo: 10 000 wywołań miesięcznie, 100 na minutę, rok historii dziennej, wymagane przypisanie źródła ([CoinMarketCap Academy](https://coinmarketcap.com/academy/tr/article/understanding-crypto-api-subscription-models-for-traders-in-2026)) | Uniwersum aktywów, metadane, ranking kapitalizacji               | **Tak, Demo → Basic przy starcie publicznym** |
| CoinMarketCap API                                              | Podobny zakres                                                                          | Basic: 15 000 kredytów miesięcznie, licencja komercyjna także na planie darmowym ([CoinMarketCap Academy](https://coinmarketcap.com/academy/ru/article/understanding-crypto-api-subscription-models-for-traders-in-2026))                    | Zapasowe źródło metadanych                                       | Adapter, wyłączony domyślnie                  |
| DefiLlama                                                      | TVL, stablecoiny, przychody protokołów                                                  | Bezpłatne                                                                                                                                                                                                                                    | Dane fundamentalne DeFi                                          | **Tak, od E4**                                |
| alternative.me                                                 | Indeks Fear & Greed                                                                     | Bezpłatne                                                                                                                                                                                                                                    | Sentyment zbiorczy                                               | **Tak**                                       |
| RSS (CoinDesk, Cointelegraph, The Block, Decrypt, blogi giełd) | Nagłówki i leady                                                                        | Bezpłatne                                                                                                                                                                                                                                    | News & Sentiment Agent                                           | **Tak**                                       |
| mempool.space, Etherscan                                       | Wybrane dane on-chain                                                                   | Darmowe limity                                                                                                                                                                                                                               | On-chain Agent (zakres ograniczony)                              | Tak, P1                                       |
| FRED                                                           | Makro (stopy, indeks dolara)                                                            | Bezpłatne                                                                                                                                                                                                                                    | Cross-Asset Agent                                                | Tak, P1                                       |
| Tardis.dev                                                     | Tickowe order booki, transakcje, likwidacje                                             | Bez klucza dostępny pierwszy dzień każdego miesiąca ([Tardis docs](https://docs.tardis.dev/node.js-client)); płatnie od 450 USD/mies. (Academic) ([Coinranking](https://coinranking.com/blog/best-historical-crypto-data-apis/))             | Badania mikrostruktury na próbkach                               | Tylko darmowe próbki; zakup odroczony         |
| CoinAPI                                                        | Agregat 350+ giełd                                                                      | Brak planu darmowego, 25 USD kredytu; plany od 79 USD ([NexusFi](https://nexusfi.com/d/data-providers/coinapi/))                                                                                                                             | –                                                                | Nie (koszt bez przewagi nad giełdami)         |
| CoinDesk Data (dawniej CryptoCompare)                          | Agregaty, newsy                                                                         | Darmowy plan wycofany 21 maja 2026 ([CoinGecko](https://coingecko.com/learn/coindesk-api-alternatives?locale=en))                                                                                                                            | –                                                                | Nie                                           |
| Kaiko                                                          | Dane instytucjonalne                                                                    | Od ok. 1000 USD/mies. ([Coinranking](https://coinranking.com/blog/best-historical-crypto-data-apis/))                                                                                                                                        | –                                                                | Nie                                           |

**Uniwersum aktywów:** top 150 par spot w USDT/USDC według wolumenu na co najmniej dwóch z czterech giełd, aktualizowane raz w tygodniu. Wymaganie dwóch giełd pozwala wykrywać błędne dane jednego źródła.

**Historia:** świece 1 h i 1 d od 2019 roku (lub od debiutu aktywa), 1 min z ostatnich 2 lat dla top 30 par. OKX udostępnia osobny endpoint `history-candles` do długiej historii ([OKX API client docs](https://mintlify.com/tiagosiebler/okx-api/rest-client/market-data)).

### Giełdy dla Trading Bota

To osobna lista: liczy się jakość API zleceń, środowisko testowe i uprawnienia kluczy, nie zasięg danych.

| Giełda            | Środowisko testowe                                                                                                                                   | Kolejność |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| OKX               | Demo trading przez ten sam endpoint z nagłówkiem `x-simulated-trading: 1` ([okx-demo-trading-api](https://github.com/vipfhe39/okx-demo-trading-api)) | 1         |
| Bybit             | Osobny testnet (`api-testnet.bybit.com`) oraz demo na mainnecie ([NautilusTrader](https://nautilustrader.io/docs/latest/integrations/bybit/))        | 2         |
| Kraken            | Konto demo dla kontraktów futures                                                                                                                    | 3         |
| Coinbase Advanced | Środowisko sandbox                                                                                                                                   | 4         |

Wszystkie integracje idą przez ccxt z własną warstwą adaptera, która normalizuje błędy, statusy zleceń i precyzję cen. Dostępność każdej giełdy dla użytkowników z Polski trzeba sprawdzić przy włączaniu integracji.

### Dane on-chain Solany (skaner tokenów, E18)

| Źródło                | Dane                                                          | Koszt i ograniczenia                                                                                                                                    | Rola                           |
| --------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| Helius (RPC Solany)   | Konta, transakcje, posiadacze tokenów                         | Free: 1 mln kredytów miesięcznie, 10 zapytań RPC na sekundę; Developer: 49 USD/mies., 10 mln kredytów ([Helius](https://helius.dev/docs/billing/plans)) | Główny czytnik on-chain        |
| Publiczne RPC Solany  | Te same dane, niższe limity                                   | Bezpłatne, niestabilne pod obciążeniem                                                                                                                  | Zapas                          |
| PumpPortal (Data API) | Strumień nowych tokenów i transakcji pump.fun przez websocket | Bezpłatne w ramach limitów; nieoficjalne API strony trzeciej ([PumpPortal](https://uithub.com/thetateman/Pump-Fun-API))                                 | Strumień premier, za adapterem |
| DexScreener API       | Ceny i płynność par po wyjściu z krzywej                      | Bezpłatne z limitami                                                                                                                                    | Dane rynkowe tokenów           |

### Zdarzenia i newsy (Agent Zdarzeń, E10a)

| Źródło                                            | Dane                                                                | Koszt i ograniczenia                                                                                                         | Rola                                                                              |
| ------------------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| CryptoPanic API                                   | Newsy kryptowalutowe z sentymentem w czasie rzeczywistym            | Plan darmowy, 5 zapytań na sekundę ([CryptoPanic](https://cryptopanic.com/developers/api/about))                             | Główny strumień newsów krypto                                                     |
| GDELT                                             | Światowe newsy w ponad 100 językach, tematy, podmioty, ton          | Bezpłatne, bez klucza; aktualizacja co ok. 15 minut ([J.A. Watte](https://jwatte.com/blog/gdelt-open-data-kalev-leetaru.md)) | Zdarzenia spoza krypto (spółki, polityka, makro); baza historyczna do event study |
| RSS wydawców i blogi giełd                        | Nagłówki, ogłoszenia listingów i delistingów                        | Bezpłatne                                                                                                                    | Szybkie potwierdzenia, źródła oficjalne                                           |
| SEC EDGAR, kalendarz Fed, publikacje danych makro | Dokumenty urzędowe, terminy FOMC i CPI                              | Bezpłatne                                                                                                                    | Kalendarz katalizatorów, potwierdzenia oficjalne                                  |
| DefiLlama (hacki)                                 | Historia exploitów protokołów                                       | Bezpłatne                                                                                                                    | Pamięć zdarzeń typu hack                                                          |
| Polymarket (Gamma API, tylko odczyt)              | Szanse na zdarzenia: decyzje w sprawie ETF, banki centralne, wybory | Bezpłatne, bez klucza i portfela (Polymarket docs)                                                                           | Czujnik oczekiwań przed zdarzeniem; bez handlu                                    |
| DefiLlama (zbiór emisji)                          | Harmonogramy odblokowań i emisji tokenów                            | Otwarty zbiór danych, bez klucza                                                                                             | Kalendarz katalizatorów: odblokowania podaży                                      |

X (Twitter) i Telegram nie są w pierwszej wersji: oficjalny dostęp do X jest płatny, a zbieranie danych z kanałów Telegrama wymaga osobnej analizy regulaminu. Wracamy do nich, gdy dane z Ledgera pokażą, że opóźnienie obecnych źródeł realnie obniża trafność.

Dla porównania kosztów: od lutego 2026 X rozlicza dostęp do API za użycie, ok. 0,005 USD za każdy odczytany wpis, bez darmowego planu ([ScrapeCreators](https://scrapecreators.com/blog/twitter-pay-per-use-api)). 200 kont po 20 wpisów dziennie to ok. 120 tys. odczytów, czyli ok. 600 USD miesięcznie, więcej niż cała reszta infrastruktury.

## 4. Hosting i infrastruktura

Oracle Cloud Always Free wystarczy na całą fazę budowy i zamkniętą betę, ale nie jako jedyna produkcja publicznej usługi. Google Cloud nie nadaje się na rdzeń (za mała darmowa maszyna, drogi zarządzany Postgres), za to dostarcza Gemini. Frontend i ochrona sieci idą na Cloudflare.

### Porównanie darmowych zasobów

| Dostawca                    | Co jest darmowe                                                                                                                                                                                              | Czy uniesie rdzeń platformy                                                                                                       | Rola                                                                                                                                                                                                     |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Oracle Cloud Always Free    | ARM Ampere A1: od czerwca 2026 równowartość 2 OCPU / 12 GB w trybie ciągłym ([terminalbytes](https://terminalbytes.com/oracle-cloud-free-tier-changes-2026)); 2 mikro-VM AMD (1/8 OCPU, 1 GB); 200 GB dysków | Tak, na etapie budowy: Postgres/Timescale, Valkey, API i workery dla 150 par mieszczą się w 12 GB i ok. 10 GB danych po kompresji | Serwer główny E3–E15; mikro-VM na executor bota ze stałym IP                                                                                                                                             |
| Google Cloud Always Free    | 1 e2-micro (1 GB RAM) w regionach USA, 30 GB dysku, Cloud Run 2 mln zapytań miesięcznie ([agentdeals](https://agentdeals.dev/gcp-free-tier-2026))                                                            | Nie: 1 GB RAM nie uniesie bazy szeregów czasowych, a region USA dodaje opóźnienia do giełd i danych w UE                          | Gemini API (AI Studio); opcjonalnie Cloud Run do jednorazowych zadań                                                                                                                                     |
| Cloudflare (Free)           | CDN, WAF, DNS, Workers, R2 (ok. 10 GB)                                                                                                                                                                       | Nie dla obliczeń, tak dla frontu i plików                                                                                         | Frontend, ochrona, archiwum Parquet, kopie                                                                                                                                                               |
| Hetzner / OVHcloud (płatne) | –                                                                                                                                                                                                            | Tak, przewidywalnie                                                                                                               | Kandydat na produkcję; ceny Hetznera wzrosły w 2026 i część planów była niedostępna ([bitdoze](https://www.bitdoze.com/md/es/hetzner-cloud-precios-2026.md)), więc decyzja przy E16 po aktualnym cenniku |

### Wybrany układ

**Faza budowy (E3–E15):**

- Konto Oracle z regionem domowym w UE (Frankfurt lub Amsterdam; region domowy jest nieodwracalny, a Always Free działa tylko w nim). Od razu przejście na **Pay As You Go z alarmem budżetu 1 USD**: zasoby Always Free pozostają darmowe, a konto nie podlega odzyskiwaniu bezczynnych instancji i ograniczeniom końca okresu próbnego.
- VM A1: 2 OCPU / 12 GB, Ubuntu 24.04 ARM, 150 GB dysku na dane. Docker Compose: `postgres` (TimescaleDB), `valkey`, `api`, `worker` ×2, `ingest`, `scheduler`, `mlflow`, `otel-collector`, `caddy` (reverse proxy z TLS).
- Mikro-VM AMD: `executor` bota ze zarezerwowanym publicznym IP (do białej listy IP na giełdach). Bez żadnych innych usług.
- Cloudflare: domena, DNS, proxy na API (ukrywa IP serwera), WAF, Workers z Next.js, R2 na kopie i archiwum.
- Trening ML na tym samym A1 w oknach nocnych (LightGBM na CPU); fine-tuning klasyfikatora tekstu na darmowym GPU w Google Colab lub Kaggle.

**Produkcja publiczna (od E16):** dwa warianty z decyzją w E16 na podstawie testów obciążeniowych z E15:

- **A (domyślny):** zostać w Oracle, zwiększając A1 do 4 OCPU / 24 GB (część ponad limit jest płatna) i dodając drugą VM na bazę. Zero migracji.
- **B:** przenieść rdzeń na płatny VPS w UE, jeśli Oracle okaże się niestabilny (brak pojemności A1, przerwy). Migracja to `terraform apply` + odtworzenie bazy z kopii, przetrenowane w E15.

### Dlaczego nie Supabase, Neon czy Vercel jako fundament

Darmowe plany zarządzanych baz Postgres mają limity rozmiaru i usypianie projektów, a TimescaleDB nie jest w nich dostępny w pełnym zakresie. Ingest z websocketów wymaga stale działającego procesu, czego serverless nie zapewnia. Dlatego rdzeń to własny serwer, a serverless tylko tam, gdzie pasuje (frontend).

## 5. Modele AI: zadanie → model → koszt

Najważniejsza decyzja: **modele językowe nie prognozują rynku**. Prognozy, reżimy, zmienność i anomalie liczą własne modele ML trenowane na naszych danych. LLM robi trzy rzeczy: czyta tekst (newsy), tłumaczy dowody na język użytkownika i prowadzi rozmowę z narzędziami. Tam, gdzie wystarcza mały model lokalny, nie płacimy za API.

### Ceny modeli komercyjnych (USD za 1 mln tokenów, wejście / wyjście)

| Model                          | Cena                                                                                                                        | Uwagi                                                                                                                                                              |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Claude Haiku 5.5               | 0,10 / 0,50 (prompt do 100 tys. tokenów); 0,50 / 2,50 powyżej ([Apidog](https://apidog.com/blog/claude-haiku-5-5-pricing/)) | Batch API: 50% taniej                                                                                                                                              |
| Claude Sonnet 5.5              | 2 / 10; Batch 1 / 5 ([Apidog](https://apidog.com/blog/claude-sonnet-5-5-pricing/))                                          | Rozumowanie, praca z narzędziami                                                                                                                                   |
| GPT-5.6 Luna / Terra           | 1 / 6 oraz 2,50 / 15 ([BenchLM](https://benchlm.ai/openai/api-pricing))                                                     | Zapas dla zadań złożonych                                                                                                                                          |
| Gemini 2.5 Flash-Lite          | 0,10 / 0,40 ([CostBench](https://costbench.com/software/llm-api-providers/google-gemini-api/))                              | Darmowy plan z limitami; na darmowym planie treści mogą służyć do ulepszania produktów Google ([Puter](https://developer.puter.com/tutorials/gemini-api-pricing/)) |
| DeepSeek V4 Flash (OpenRouter) | 0,14 / 0,28 ([ComputePrices](https://computeprices.com/providers/openrouter/models/deepseek-v4-flash))                      | Model otwarty, zapas cenowy                                                                                                                                        |

### Zestawienie zadań

| Zadanie                                                     | Model lub technologia                                                                                        | Sposób użycia                                                               | Uzasadnienie                                                                                                                     | Koszt miesięczny (start publiczny)       |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| Prognoza kierunku i kwantyli zwrotu                         | LightGBM (własny)                                                                                            | Trening tygodniowy, inferencja w workerze po zamknięciu świecy              | Dane tablicowe; modele gradient boosting są szybkie, kalibrowalne i interpretowalne (SHAP); LLM nie są kalibrowanymi prognostami | 0                                        |
| Reżim rynku                                                 | Ukryty model Markowa (hmmlearn)                                                                              | Dopasowanie tygodniowe, filtracja online                                    | Klasyczna, mierzalna metoda dla reżimów zmienności                                                                               | 0                                        |
| Zmienność, VaR, CVaR                                        | GARCH (biblioteka arch) + EWMA                                                                               | Co godzinę per aktyw                                                        | Standard branżowy, łatwy do walidacji                                                                                            | 0                                        |
| Anomalie i pompy                                            | Isolation Forest + CUSUM                                                                                     | Strumieniowo na cechach wolumenu i ceny                                     | Brak etykiet; metody nienadzorowane                                                                                              | 0                                        |
| Sentyment nagłówków                                         | Własny klasyfikator: fine-tuning małego enkodera (punkt odniesienia: FinBERT)                                | Inferencja na CPU w workerze, milisekundy na nagłówek                       | Tysiące nagłówków dziennie; lokalnie za darmo i bez limitów                                                                      | 0 (trening na darmowym GPU w Colab)      |
| Ekstrakcja zdarzeń z newsów                                 | Claude Haiku 5.5; zapas Gemini 2.5 Flash-Lite                                                                | Wymuszony schemat JSON, tylko dla ok. 10% newsów o wysokiej istotności      | Wymaga rozumienia kontekstu (hack, listing, regulacja); niski koszt                                                              | ok. 2 USD                                |
| Narracja (Narrator)                                         | Claude Haiku 5.5 przez Batch API                                                                             | Generowanie z gotowych dowodów, PL i EN w jednym wywołaniu; walidator liczb | Najniższa cena wejścia wśród głównych dostawców przy dobrej jakości języka                                                       | 8–15 USD (150 par × 6 narracji dziennie) |
| Adwokat diabła                                              | Claude Haiku 5.5                                                                                             | Ten sam zestaw dowodów, inna instrukcja                                     | Zadanie krótkie i ograniczone do faktów                                                                                          | ok. 3 USD                                |
| Czat "Zapytaj rynek"                                        | Claude Haiku 5.5 domyślnie; Claude Sonnet 5.5 w trybie analizy pogłębionej (limit 1 dziennie na użytkownika) | Narzędzia: zapytania do dowodów, cech, Ledgera, newsów                      | Odpowiedzi tylko z danych platformy; mocniejszy model tam, gdzie potrzebne wieloetapowe rozumowanie                              | ok. 30 USD przy 1000 pytań dziennie      |
| Raport tygodniowy, generator strategii z języka naturalnego | Claude Sonnet 5.5                                                                                            | Wynik w ściśle walidowanym DSL strategii                                    | Wymaga precyzyjnej, ustrukturyzowanej odpowiedzi                                                                                 | 5–20 USD                                 |
| Embeddingi (RAG)                                            | Otwarty model wielojęzyczny (np. bge-m3) na CPU + pgvector                                                   | Indeks newsów, dowodów, dokumentacji                                        | Obsługuje polski; bez kosztów API                                                                                                | 0                                        |
| Ocena jakości odpowiedzi LLM                                | Model innej rodziny niż generator (Gemini Flash-Lite lub GPT-5.x)                                            | Offline na zbiorze wzorcowym przy każdej zmianie promptu                    | Unikamy oceniania modelu przez ten sam model                                                                                     | ok. 2 USD                                |
| Praca deweloperska nad promptami                            | Darmowy plan Gemini                                                                                          | Tylko dane publiczne                                                        | Zero kosztów w fazie budowy                                                                                                      | 0                                        |

### Modele samouczenia i modele ilościowe

| Zadanie                    | Model                                                 | Sposób użycia                                                     | Etap | Koszt |
| -------------------------- | ----------------------------------------------------- | ----------------------------------------------------------------- | ---- | ----- |
| Dynamiczna uczciwa wartość | Filtr Kalmana                                         | Agent Trend; odchylenie od uczciwej wartości jako fakt w dowodzie | E7   | 0     |
| Tempo powrotu do średniej  | Proces Ornsteina-Uhlenbecka (estymacja κ i półokresu) | Agent Mean Reversion                                              | E7   | 0     |
| Zaufanie do agentów        | Hedge (wagi multiplikatywne)                          | Fuzja, per reżim                                                  | E9   | 0     |
| Filtr decyzji              | Meta-labeling, LightGBM                               | Czy realizować sygnał i jak dużą pozycją                          | E11a | 0     |
| Dobór strategii            | Kontekstowy bandyta (Thompson sampling)               | Wybór strategii per reżim, eksploracja tylko w paper              | E11a | 0     |
| Strojenie parametrów       | Optuna z celem Deflated Sharpe Ratio                  | Miesięcznie, zmiany maks. ±20%                                    | E11a | 0     |
| Ryzyko tokena on-chain     | Reguły + kalibrowana regresja logistyczna             | Ocena 0–100 w skanerze                                            | E18  | 0     |

**Agent Zdarzeń (E10a)** łączy kilka metod:

- ekstrakcję struktury zdarzenia (Claude Haiku 5.5, schemat JSON, tylko dla zdarzeń wysokiej istotności),
- wyszukiwanie historycznych odpowiedników (embeddingi bge-m3 w pgvector),
- klasyczne badanie zdarzeń (nadwyżkowe stopy zwrotu względem modelu rynkowego),
- model fazy reakcji (LightGBM: kontynuacja albo odbicie po szoku).

Dodatkowy koszt LLM to ok. 5–15 USD miesięcznie.

**Suma LLM:** faza budowy 0–5 USD miesięcznie, start publiczny ok. 50–75 USD, przy ok. 10 tys. aktywnych użytkowników ok. 150–250 USD (głównie czat; koszt narracji się nie zmienia).

### Zarządzanie wieloma modelami

- **Bramka LiteLLM** jako biblioteka w module `llm`. Kod używa aliasów ról (`narrator`, `extractor`, `chat`, `deep`, `judge`), a nie nazw modeli. Mapowanie alias → model główny → zapasowe jest w pliku konfiguracyjnym.
- **Przypięte wersje modeli** (identyfikatory z datą tam, gdzie dostawca je oferuje); zmiana wersji tylko przez PR z wynikami ewaluacji.
- **Prompty jako pliki** (`prompts/<rola>/<wersja>.yaml`) z numerem wersji zapisywanym w każdym wyniku.
- **Odporność:** timeout, 2 ponowienia z backoffem, przełączenie na model zapasowy, a gdy wszystkie zawiodą, narracja z szablonu bez LLM. Wyłącznik obwodu per dostawca.
- **Budżety:** dzienny limit kosztów per alias i per użytkownik w Valkey; po przekroczeniu przełączenie na tańszy model lub szablon.
- **Telemetria:** Langfuse zapisuje każde wywołanie (koszt, opóźnienie, wersja promptu, wynik walidacji). Dane użytkowników są pseudonimizowane przed wysłaniem do dostawcy.

## 6. Trenowanie i dostosowanie modeli

Odpowiedź krótka: **nie trenujemy GPT, Claude ani Gemini na własnych danych**. W listopadzie 2026 to albo niemożliwe, albo nieopłacalne. Specyfikę rynku kryptowalut wnosimy do systemu przez własne modele ML, dane w narzędziach i RAG oraz fine-tuning małych modeli otwartych, które możemy trzymać u siebie.

### Co dziś pozwalają dostawcy

| Dostawca                                      | Fine-tuning                                                                                                                                                                                                                                                                                                                                                                                      | Konsekwencja dla nas                                                                            |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| OpenAI                                        | Samoobsługowy fine-tuning jest wygaszany: od 7 maja 2026 niedostępny dla nowych organizacji, a nowe zadania kończą się 6 stycznia 2027 ([CostBench](https://www.costbench.com/software/fine-tuning-apis/openai-fine-tuning/))                                                                                                                                                                    | Nie mamy dostępu; nie budujemy na tym                                                           |
| Google (Vertex AI)                            | Supervised fine-tuning dla Gemini 2.5 Pro, Flash i Flash-Lite ([Vertex AI docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini-tuning)); dla modeli 3.x jeszcze niedostępny według pytań użytkowników na forum Google ([Google Developer forum](https://discuss.google.dev/t/when-will-supervised-fine-tuning-be-available-for-gemini-3-x-models-on-vertex-ai/346487)) | Możliwe, ale tylko na starszej generacji, z płatnym hostingiem modelu i uzależnieniem od Vertex |
| Anthropic (Claude API)                        | Brak samoobsługowego fine-tuningu w publicznym API (do potwierdzenia w dokumentacji przed decyzją)                                                                                                                                                                                                                                                                                               | Dostosowanie przez prompty, narzędzia i przykłady                                               |
| Modele otwarte (Qwen, Gemma, Llama, DeepSeek) | Pełna kontrola: LoRA lub QLoRA lokalnie albo w usługach zarządzanych, np. Vertex tunuje Qwen 3 32B i Gemma 3 27B ([DevelopersDigest](https://www.developersdigest.tech/blog/openai-fine-tuning-shutdown-alternatives))                                                                                                                                                                           | Opcja na później, gdy będziemy mieli własny zbiór i ewaluację                                   |

### Którą metodę kiedy

| Potrzeba                                 | Metoda                                                                             | Przykład u nas                                                                 |
| ---------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Model ma znać aktualne fakty             | Narzędzia (function calling) i RAG                                                 | Czat pobiera bieżące dowody i newsy z bazy; wiedza nigdy nie jest "wtrenowana" |
| Model ma pisać w naszym stylu i formacie | Prompt systemowy + 5–10 przykładów + wymuszony schemat                             | Narrator, adwokat diabła                                                       |
| Tania klasyfikacja w dużej skali         | Fine-tuning małego modelu otwartego                                                | Sentyment i typ zdarzenia w nagłówkach                                         |
| Obniżenie kosztów drogiego zadania LLM   | Destylacja: duży model generuje etykiety, mały model otwarty uczy się je odtwarzać | Ekstrakcja zdarzeń, gdy wolumen przekroczy kilka tysięcy dziennie              |
| Prognozy liczbowe                        | Własne modele ML na cechach                                                        | LightGBM, GARCH, HMM                                                           |

### Własne modele ML: tak, to rdzeń

Budujemy je, bo tylko one dają mierzalne, skalibrowane prognozy, które można uczciwie rozliczać. Cykl życia:

1. **Zbieranie danych:** ingest zapisuje surowe dane; feature store liczy cechy point-in-time; etykiety (zwrot w horyzoncie, przekroczenie poziomu) powstają automatycznie po upływie horyzontu.
2. **Zbiory treningowe:** migawki Parquet na R2 z hashem zawartości; każdy trening zapisuje w MLflow hash zbioru, wersję kodu (commit) i parametry.
3. **Walidacja:** walk-forward z purgingiem i embargiem; obowiązkowe punkty odniesienia; zbiór zamknięty (ostatnie 6 miesięcy) otwierany tylko przy decyzji o promocji.
4. **Promocja champion/challenger:** nowy model działa 14 dni w trybie cienia (prognozy zapisywane, nieużywane w fuzji); przechodzi, jeśli poprawia Brier score o istotną statystycznie wartość (test Diebolda-Mariano, p < 0,05) i nie pogarsza kalibracji.
5. **Monitoring:** dryf cech (PSI), dryf trafności w Ledgerze, alarm przy spadku poniżej punktu odniesienia przez 7 dni.
6. **Retrening:** tygodniowy, automatyczny; promocja zawsze przez bramkę z punktu 4.

### Zbiór tekstowy dla klasyfikatora newsów

1. Zbieramy nagłówki z RSS od pierwszego dnia E4.
2. Claude Haiku 5.5 wstępnie etykietuje sentyment i typ zdarzenia (tanio, wsadowo).
3. Ręczna weryfikacja 1500–2000 przykładów w Label Studio (darmowe, self-hosted), z miarą zgodności.
4. Fine-tuning małego enkodera na darmowym GPU (Colab lub Kaggle); porównanie z FinBERT i z LLM na zbiorze testowym.
5. Model produkcyjny trafia do rejestru MLflow; inferencja na CPU.

## 7. Narzędzia zewnętrzne

**Lovable: tak, ale tylko do prototypów UX, nie jako kod produkcyjny.** Lovable generuje aplikacje React + Vite z backendem Supabase (Lovable Cloud) i synchronizuje kod z GitHubem ([Review AI Tool](https://blog.reviewaitool.com/tag/lovable-review/)). Nasza architektura ma własny backend FastAPI, własną bazę i SSR w Next.js, więc kod z Lovable musiałby zostać przepisany, a generowanie kolejnych poprawek zużywa kredyty i łatwo wprowadza regresje. Lovable ma jednak realną przewagę w tempie budowy klikalnych prototypów do testów z użytkownikami. Plan Pro kosztuje od 25 USD miesięcznie, a darmowy daje 5 kredytów dziennie ([HostAdvice](https://ca.hostadvice.com/hosting-company/lovable-reviews/pricing/)); wykupujemy Pro na jeden miesiąc w E12.

Oba stosy używają Tailwind i shadcn/ui, więc komponenty wizualne z prototypu da się przenieść do Next.js z niewielkimi zmianami.

### Zestaw narzędzi

| Zadanie                                      | Narzędzie                                                               | Kiedy (etap) | Koszt                   | Jak przekazujesz mi wynik                                                      |
| -------------------------------------------- | ----------------------------------------------------------------------- | ------------ | ----------------------- | ------------------------------------------------------------------------------ |
| System projektowy, makiety                   | Figma (plan darmowy)                                                    | E12          | 0                       | Link do pliku lub eksport PNG ekranów                                          |
| Klikalne prototypy do testów z użytkownikami | Lovable Pro, 1 miesiąc                                                  | E12          | ok. 25 USD              | Synchronizacja z osobnym repo GitHub; podajesz link, a ja przenoszę komponenty |
| Implementacja kodu                           | Claude Code (w terminalu lub tutaj)                                     | E0–E17       | Wg Twojego planu Claude | Praca bezpośrednio na repozytorium                                             |
| Przegląd PR i bezpieczeństwa                 | CodeQL, Dependabot, gitleaks, Trivy (GitHub Actions)                    | od E1        | 0 dla repo publicznego  | Automatycznie w PR                                                             |
| Zarządzanie bazą                             | Alembic (migracje), pgAdmin lub DBeaver lokalnie                        | od E2        | 0                       | –                                                                              |
| Eksperymenty ML                              | MLflow (self-hosted), Optuna, Jupyter                                   | od E8        | 0                       | Link do eksperymentu w MLflow                                                  |
| Etykietowanie danych tekstowych              | Label Studio (self-hosted)                                              | E10          | 0                       | Eksport JSON do repo danych                                                    |
| Trening na GPU                               | Google Colab lub Kaggle (darmowe GPU)                                   | E10          | 0                       | Model trafia do MLflow                                                         |
| Obserwowalność LLM                           | Langfuse Cloud (plan darmowy) lub self-hosted                           | od E10       | 0                       | –                                                                              |
| Monitoring aplikacji                         | Grafana Cloud (darmowy), Sentry (darmowy), Better Stack lub UptimeRobot | od E3        | 0                       | Alerty e-mail i Telegram                                                       |
| Testy obciążeniowe                           | k6                                                                      | E15          | 0                       | Raport w CI                                                                    |
| Testy E2E                                    | Playwright                                                              | od E12       | 0                       | Raport HTML w artefaktach CI                                                   |
| Testy kontraktowe API                        | Schemathesis (z OpenAPI)                                                | od E6        | 0                       | W CI                                                                           |
| E-mail transakcyjny                          | Resend lub Brevo (plany darmowe)                                        | E6, E13      | 0                       | –                                                                              |
| Powiadomienia                                | Telegram Bot API, Web Push (VAPID)                                      | E13          | 0                       | –                                                                              |

### Sposób pracy z narzędziami

W etapie, który korzysta z zewnętrznego narzędzia, przygotuję dla Ciebie gotowy prompt lub instrukcję konfiguracji krok po kroku. Wynik wraca do mnie zawsze przez repozytorium GitHub (kod) albo link (Figma, MLflow). Nic nie trafia do głównego repo bez przeglądu i testów.

## 8. Publiczne repozytorium i sekrety

Zasada: **w repozytorium może być tylko to, co mogłoby zostać wydrukowane na pierwszej stronie gazety**. Sekrety są albo zaszyfrowane (SOPS), albo trzymane poza repo (GitHub Environments, serwer), a pięć niezależnych warstw pilnuje, żeby nic nie wyciekło.

### Struktura repozytorium

```
platform/
  apps/web/              Next.js
  services/platform/     pakiet Python (api, worker, ingest, scheduler)
  services/executor/     executor bota (osobny obraz)
  packages/contracts/    OpenAPI, JSON Schema zdarzeń, wygenerowany klient TS
  ml/                    trening, notatniki (bez danych)
  prompts/               prompty LLM z wersjami
  infra/terraform/       Oracle, Cloudflare
  infra/ansible/         konfiguracja serwerów
  infra/compose/         docker-compose dla dev, staging, prod
  infra/secrets/         pliki *.enc.yaml zaszyfrowane SOPS
  docs/adr/              decyzje architektoniczne
  tests/e2e/             Playwright
  .github/workflows/     CI/CD
```

### Klasy sekretów i miejsce przechowywania

| Klasa                         | Przykłady                                               | Gdzie                                                                                                                               | Kto ma dostęp              |
| ----------------------------- | ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| Sekrety infrastruktury        | Klucze API Oracle i Cloudflare, token GHCR              | GitHub Environments (`staging`, `production`) z wymaganym zatwierdzeniem                                                            | Tylko workflow wdrożeniowy |
| Sekrety aplikacji             | Hasła do bazy, klucze LLM, CoinGecko, klucz podpisu JWT | `infra/secrets/<env>.enc.yaml` zaszyfrowane SOPS kluczem age; klucz prywatny age tylko na serwerze i w menedżerze haseł właściciela | Serwer danego środowiska   |
| Klucze API giełd użytkowników | Klucz i sekret do konta giełdowego                      | Baza executora, szyfrowanie kopertowe: klucz danych per użytkownik (AES-256-GCM), klucz główny w OCI Vault                          | Wyłącznie proces executora |
| Dane osobowe                  | E-mail, ustawienia                                      | Baza, szyfrowanie dysku, minimalizacja                                                                                              | API przez uprawnienia      |
| Lokalny development           | `.env.local`                                            | Tylko na Twoim komputerze, w `.gitignore`; wzór w `.env.example` bez wartości                                                       | Ty                         |

### Pięć warstw ochrony przed wyciekiem

1. **pre-commit z gitleaks** lokalnie: blokuje commit z czymś, co wygląda na sekret.
2. **GitHub Secret Scanning + Push Protection** (darmowe dla repo publicznych): blokuje push.
3. **gitleaks w CI** na każdym PR, z pełną historią.
4. **Brak danych w repo:** żadnych zrzutów bazy, plików `.parquet`, `.csv` z danymi użytkowników ani logów; reguły w `.gitignore` i kontrola rozmiaru plików w CI.
5. **Procedura incydentu:** wyciek = natychmiastowa rotacja klucza u dostawcy (nie tylko usunięcie z historii), wpis w dzienniku incydentów.

### Proces developmentu

- Gałąź `main` chroniona: tylko przez PR, wymagane zielone CI i bramka etapu, zakaz force-push, podpisane commity.
- Gałęzie `feat/E<nr>-<opis>`; jeden PR = jedno zadanie z roadmapy.
- Konwencja Conventional Commits; changelog i wersje generowane automatycznie (release-please).
- Środowiska: `local` (Docker Compose), `staging` (ten sam serwer Oracle, osobna baza i porty, w fazie budowy), `production` (od E16).
- Licencja repo: do wyboru w E1 (rekomendacja: AGPL-3.0 dla platformy, żeby kopie hostowane też musiały udostępniać kod; alternatywnie MIT).

## 9. Koszty

Platformę da się zbudować i przetestować za ok. 50 USD w całym okresie budowy (domena + jeden miesiąc Lovable). Publiczna wersja kosztuje ok. 60–150 USD miesięcznie, a dominującym kosztem przy wzroście jest czat z LLM, nie infrastruktura. Kwoty to szacunki z cenników z sekcji 3–7; ceny Oracle ponad limit darmowy i domen należy potwierdzić przy zakupie.

| Kategoria                                          | Składniki                                                                                                                        | Kwota           |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| Rozpoczęcie projektu (jednorazowo)                 | Domena (ok. 10–20 USD rocznie), konta w usługach (darmowe)                                                                       | 10–20 USD       |
| Development i testy (miesięcznie, E0–E15)          | Oracle Always Free (0), Cloudflare (0), GitHub (0), LLM w darmowym planie Gemini + testy Claude (0–5), dane (0)                  | 0–5 USD         |
| Jednorazowo w trakcie budowy                       | Lovable Pro na 1 miesiąc w E12                                                                                                   | ok. 25 USD      |
| Uruchomienie publicznej wersji (jednorazowo, E16)  | Ewentualne powiększenie A1 lub VPS, test obciążeniowy (k6 lokalnie, 0)                                                           | 0–30 USD        |
| Utrzymanie miesięczne (do ok. 5 tys. użytkowników) | Serwer ponad limit darmowy 0–30, kopie R2 0–2, LLM 50–75, CoinGecko Basic 0–35 (jeśli Demo nie wystarczy), e-mail i monitoring 0 | ok. 60–140 USD  |
| Większa skala (10–50 tys. użytkowników)            | Dwa serwery aplikacji + serwer bazy 80–200, LLM 150–250, dane 35–129, płatne plany monitoringu 0–30                              | ok. 270–610 USD |

Skaner on-chain (E18) startuje na darmowym planie Helius. Przy większym ruchu dochodzi plan Developer za 49 USD miesięcznie, co trzeba zatwierdzić przez ADR.

### Mechanizmy kontroli kosztów

- Alarm budżetowy w Oracle (1 USD w fazie budowy), limity wydatków u każdego dostawcy LLM.
- Dzienne limity kosztów LLM per rola i per użytkownik w bramce (sekcja 5).
- Panel kosztów w Grafanie: koszt LLM na dzień, wywołania API danych, zużycie dysku.
- Przegląd kosztów co miesiąc w E17; każdy nowy płatny składnik wymaga ADR.

## Źródła

- [CoinMarketCap Academy: Crypto API subscription models 2026](https://coinmarketcap.com/academy/tr/article/understanding-crypto-api-subscription-models-for-traders-in-2026)
- [CoinGecko: CoinDesk API alternatives (wycofanie darmowego planu CoinDesk)](https://coingecko.com/learn/coindesk-api-alternatives?locale=en)
- [Coinranking: Best historical crypto data APIs 2026](https://coinranking.com/blog/best-historical-crypto-data-apis/)
- [NexusFi: CoinAPI](https://nexusfi.com/d/data-providers/coinapi/)
- [Tardis.dev: Node.js client](https://docs.tardis.dev/node.js-client)
- [OKX API client: market data](https://mintlify.com/tiagosiebler/okx-api/rest-client/market-data)
- [OKX demo trading API](https://github.com/vipfhe39/okx-demo-trading-api)
- [NautilusTrader: Bybit](https://nautilustrader.io/docs/latest/integrations/bybit/)
- [terminalbytes: Oracle Cloud free tier changes 2026](https://terminalbytes.com/oracle-cloud-free-tier-changes-2026)
- [agentdeals: GCP Free Tier 2026](https://agentdeals.dev/gcp-free-tier-2026)
- [bitdoze: Precios de Hetzner Cloud en 2026](https://www.bitdoze.com/md/es/hetzner-cloud-precios-2026.md)
- [Apidog: Claude Haiku 5.5 pricing](https://apidog.com/blog/claude-haiku-5-5-pricing/)
- [Apidog: Claude Sonnet 5.5 pricing](https://apidog.com/blog/claude-sonnet-5-5-pricing/)
- [BenchLM: OpenAI API pricing](https://benchlm.ai/openai/api-pricing)
- [CostBench: Google Gemini API](https://costbench.com/software/llm-api-providers/google-gemini-api/)
- [ComputePrices: DeepSeek V4 Flash on OpenRouter](https://computeprices.com/providers/openrouter/models/deepseek-v4-flash)
- [CostBench: OpenAI fine-tuning (wygaszanie)](https://www.costbench.com/software/fine-tuning-apis/openai-fine-tuning/)
- [Vertex AI: Gemini tuning](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini-tuning)
- [DevelopersDigest: OpenAI fine-tuning shutdown alternatives](https://www.developersdigest.tech/blog/openai-fine-tuning-shutdown-alternatives)
- [HostAdvice: Lovable pricing](https://ca.hostadvice.com/hosting-company/lovable-reviews/pricing/)
- [Review AI Tool: Lovable review](https://blog.reviewaitool.com/tag/lovable-review/)
- [Helius: Plans and pricing](https://helius.dev/docs/billing/plans)
- [PumpPortal: Pump.fun API (README)](https://uithub.com/thetateman/Pump-Fun-API)
- [OurCryptoTalk: Pump.fun traders losing money](https://ourcryptotalk.com/news/pump-fun-96-percent-traders-losing-money)
- [CryptoPanic: API plans](https://cryptopanic.com/developers/api/about)
- [J.A. Watte: GDELT open data](https://jwatte.com/blog/gdelt-open-data-kalev-leetaru.md)
- [Polymarket: Market data overview](https://docs.polymarket.com/market-data/overview.md)
- [ScrapeCreators: X API pricing 2026](https://scrapecreators.com/blog/twitter-pay-per-use-api)
- [CNBC: Weekend trading of Nvidia scandal shines light on new financial products](https://www.cnbc.com/2026/11/09/weekend-trading-of-nvidia-scandal-shines-light-on-new-financial-products.html)
- [The Block: Nvidia perps slide as market reacts to CEO scandal](https://www.theblock.co/news/defi/2026-11-08-nvidia-perps-slide-jensen-huang-436047)
- [CNBC: Nvidia stock falls 9% as investors await Jensen Huang's fate](https://www.cnbc.com/2026/11/12/nvidia-nvda-jensen-huang-second-affair.html)
- [CBS News: Nvidia's stock dives as board weighs move to oust CEO](https://www.cbsnews.com/news/nvidia-stock-dives-report-board-prepares-oust-jensen-huang/)
- [CoinDesk: Nvidia perps crash on Hyperliquid](https://www.coindesk.com/markets/2026/11/12/bitcoin-listless-nvidia-perps-crash-7-as-ceo-jensen-huang-reportedly-faces-the-axe)
