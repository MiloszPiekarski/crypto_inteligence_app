# Strategia testów i quality gates

Testujemy nie tylko to, czy system działa, ale czy liczy poprawnie: każdy moduł obliczeniowy ma testy względem niezależnie policzonych wartości referencyjnych, a każdy etap kończy się bramką, którą sprawdza automat, a nie deklaracja.

## 1. Zasady

### Piramida testów

| Poziom                                                 | Udział  | Czas uruchomienia | Gdzie                          |
| ------------------------------------------------------ | ------- | ----------------- | ------------------------------ |
| Jednostkowe i właściwości (Hypothesis)                 | ok. 70% | < 3 min           | Każdy push                     |
| Integracyjne (prawdziwy Postgres/Valkey w kontenerach) | ok. 20% | < 8 min           | Każdy PR                       |
| Kontraktowe, E2E, wizualne, dostępności                | ok. 10% | < 15 min          | Każdy PR do `main`             |
| Obciążeniowe, chaos, DR, ewaluacja modeli              | –       | godziny           | Nocne, tygodniowe i w bramkach |

### Definicja ukończenia zadania

1. Kod ma testy jednostkowe; pokrycie nowych linii ≥ 85% (moduły obliczeniowe: `features`, `agents`, `fusion`, `ledger`, `backtest`, `bot_core` ≥ 95%).
2. Obliczenia mają test względem wartości referencyjnej policzonej niezależnie (arkusz, inna biblioteka, wynik ręczny).
3. Zmiana kontraktu (API, zdarzenie, `Evidence`) ma zaktualizowany schemat i testy kontraktowe.
4. Zmiana zachowania analizy ma zaktualizowane pliki wzorcowe (golden files) z uzasadnieniem w opisie PR.
5. CI zielone, przegląd PR wykonany, dokumentacja i ADR zaktualizowane, jeśli zmienia się architektura.

### Polityka niepowodzeń

- **Czerwony test = zatrzymanie.** Nie wyłączamy testów, żeby przejść dalej. Test niestabilny trafia do kwarantanny maksymalnie na 7 dni z przypisanym zadaniem naprawy; w tym czasie nie liczy się do bramki, a bramka nie może przejść, jeśli dotyczy jej zakresu.
- **Diagnoza przed obejściem:** każdy błąd w bramce ma krótki zapis przyczyny w opisie poprawki.
- **Błąd na produkcji = nowy test regresyjny**, który odtwarza problem, zanim powstanie poprawka.
- **Zewnętrzne API:** testy kontraktowe na nagranych odpowiedziach w CI + codzienny test na żywym API; zmiana po stronie dostawcy jest naprawiana przed kolejnym wydaniem.

## 2. Rodzaje testów

| Rodzaj                       | Co sprawdzamy                                                                                    | Jak                                                          | Narzędzie                                           | Wynik poprawny                                      | Przy niepowodzeniu                               |
| ---------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------ | --------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------ |
| Jednostkowe                  | Funkcje i klasy w izolacji, obliczenia wskaźników, reguły                                        | Przypadki typowe i brzegowe                                  | pytest, Vitest                                      | 100% zielonych, pokrycie wg definicji ukończenia    | Blokada merge                                    |
| Właściwości                  | Niezmienniki: fuzja w [0, 1], silnik ryzyka nie przekracza limitów, brak zaglądania w przyszłość | Losowo generowane wejścia, minimalizacja kontrprzykładu      | Hypothesis                                          | Brak kontrprzykładów w 1000+ próbach                | Kontrprzykład zapisany jako stały test; poprawka |
| Integracyjne                 | Moduły z prawdziwą bazą, Valkey, kolejkami                                                       | Kontenery uruchamiane na czas testu                          | pytest + testcontainers                             | Przepływy od zdarzenia do zapisu działają           | Blokada merge                                    |
| Kontraktowe API              | Zgodność odpowiedzi z OpenAPI, brak 500                                                          | Zapytania generowane ze specyfikacji                         | Schemathesis                                        | 0 niezgodności                                      | Blokada merge                                    |
| Kontraktowe zdarzeń          | Komunikaty w strumieniach zgodne z JSON Schema                                                   | Walidacja producentów i konsumentów                          | jsonschema, pytest                                  | 100% zgodnych                                       | Blokada merge                                    |
| Kontraktowe API zewnętrznych | Format odpowiedzi giełd, CoinGecko, dostawców LLM                                                | Nagrane odpowiedzi w CI + codzienny test na żywo             | vcrpy, cron w Actions                               | Brak zmian schematu                                 | Alert; aktualizacja adaptera                     |
| End-to-end                   | Ścieżki użytkownika w przeglądarce                                                               | Scenariusze na staging z danymi testowymi                    | Playwright                                          | Zielone w 3 silnikach + mobile                      | Blokada wdrożenia                                |
| Poprawność danych            | Kompletność, spójność OHLC, zgodność ze źródłem, świeżość                                        | Reguły DQ, próbki porównywane ze źródłem                     | pytest, zadania DQ, Grafana                         | Kompletność ≥ 99,9%, 0 niewyjaśnionych rozbieżności | Dane oznaczone jako niewiarygodne; diagnoza      |
| Modele ML                    | Wyciek, odtwarzalność, jakość vs punkty odniesienia, kalibracja, dryf                            | Walk-forward, zbiór zamknięty, testy na danych syntetycznych | pytest, MLflow, Evidently lub własne PSI            | Wg bramki G8                                        | Model nie jest promowany                         |
| Modele LLM                   | Zgodność liczb, schemat, jakość, odporność na wstrzykiwanie poleceń, koszt                       | Zbiory wzorcowe przy każdej zmianie promptu lub modelu       | Langfuse datasets, pytest                           | Wg bramki G10                                       | Blokada merge zmiany promptu                     |
| Backtesting                  | Zgodność z ręcznie przeliczonymi strategiami, metryki, kolejność SL/TP                           | Strategie referencyjne                                       | pytest, empyrical                                   | Wg bramki G11                                       | Blokada                                          |
| Trading Bot                  | Silnik ryzyka, maszyna stanów, idempotencja, uzgadnianie, kill switch                            | Paper, testnet, chaos                                        | pytest, Hypothesis, testnety OKX i Bybit, Toxiproxy | Wg bramek G14a–c                                    | Blokada trybu wyższego                           |
| Bezpieczeństwo               | Podatności aplikacji, zależności, obrazów, sekrety, kontrola dostępu                             | Skanery w CI + testy ręczne wg ASVS                          | CodeQL, gitleaks, Trivy, OWASP ZAP                  | 0 wysokich i krytycznych                            | Blokada wdrożenia                                |
| Wydajność i obciążenie       | Opóźnienia, przepustowość, stabilność w czasie                                                   | Profile ruchu, test 24 h                                     | k6, pytest-benchmark, Lighthouse CI                 | NF-01, NF-02 spełnione                              | Profilowanie i poprawka                          |
| Odporność                    | Awarie zależności, sieci, restartu                                                               | Wstrzykiwanie usterek                                        | Toxiproxy, docker stop                              | Zachowanie zgodne z tabelą degradacji               | Poprawka obsługi błędów                          |
| Regresyjne                   | Brak niezamierzonych zmian wyników analizy i UI                                                  | Pliki wzorcowe ocen i backtestów, zrzuty ekranów             | pytest (golden files), Playwright screenshots       | Brak zmian lub zmiany zatwierdzone w PR             | Wyjaśnić przed merge                             |
| Dostępność UI                | WCAG 2.2 AA                                                                                      | Skan każdego widoku                                          | axe-core                                            | 0 naruszeń krytycznych i poważnych (axe)            | Blokada merge                                    |
| Odtwarzanie (DR)             | Kopie, RTO, RPO                                                                                  | Ćwiczenie na czystej maszynie                                | pgBackRest, Terraform                               | RTO ≤ 4 h, RPO wg NF-04                             | Poprawa automatyzacji                            |

## 3. Quality gates

Bramka to zestaw automatycznych sprawdzeń zapisany w pliku `gates/G<nr>.yaml` (komendy testów, progi, wymagane raporty). Etap jest zaliczony dopiero, gdy `make gate G=<nr>` przejdzie w CI na `main`, a raport trafi do `docs/gates/`. Kolumna Status służy do śledzenia postępu.

| Bramka | Etap | Kluczowe kryteria                                                                                                                     | Odblokowuje                                          | Status         |
| ------ | ---- | ------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- | -------------- |
| G0     | E0   | Konta z 2FA, klucze w menedżerze haseł, `doctor` zielony, testy połączeń                                                              | E1                                                   | Zaliczona      |
| G1     | E1   | CI zielone, blokada sekretu na 3 poziomach, ochrona `main`, ADR-001                                                                   | E2                                                   | Zaliczona      |
| G2     | E2   | Migracja 0001 w obie strony, schematy zdarzeń i OpenAPI poprawne, wymagania z ID                                                      | E3, E12a                                             | Zaliczona      |
| G3     | E3   | Odtworzenie środowiska < 30 min, udane odtworzenie kopii, alerty działają                                                             | E4, E6                                               | W toku         |
| G4     | E4   | Kompletność ≥ 99,9%, DQ wykrywa ≥ 95% błędów, 72 h bez interwencji                                                                    | E5                                                   | Nie rozpoczęto |
| G5     | E5   | Test point-in-time 100%, live = replay, wskaźniki zgodne z referencją                                                                 | E7, E8                                               | Nie rozpoczęto |
| G6     | E6   | Schemathesis i testy autoryzacji zielone, 0 IDOR, ZAP bez alertów wysokich                                                            | E12b, E13                                            | Nie rozpoczęto |
| G7     | E7   | Testy właściwości agentów, 14 dni dowodów bez luk, Ledger = ręczne przeliczenie                                                       | E8, E9                                               | Nie rozpoczęto |
| G8     | E8   | Odtwarzalność, brak wycieku, raport walk-forward, tryb cienia                                                                         | E9                                                   | Nie rozpoczęto |
| G9     | E9   | Fuzja ≤ najlepszy agent (Brier), reguły weta 100% pokryte, ablacje                                                                    | E10, E11, E13                                        | Nie rozpoczęto |
| G10    | E10  | 0 niezgodnych liczb na 500 narracjach, klasyfikator ≥ FinBERT + 5 pp., test awarii dostawców                                          | E12b                                                 | Nie rozpoczęto |
| G10a   | E10a | 0 fałszywych zdarzeń potwierdzonych, event study = ręczne przeliczenie, brak wycieku w pamięci zdarzeń, prognozy reakcji skalibrowane | E11a (strategie zdarzeniowe), E12b (karta zdarzenia) | Nie rozpoczęto |
| G11    | E11  | 5 strategii referencyjnych zgodnych, test pułapki, wydajność                                                                          | E11a, E12b (Laboratorium), E14a                      | Nie rozpoczęto |
| G11a   | E11a | Brak wycieku w etykietach, filtr decyzji z przewagą lub wyłączony, granice uczenia nienaruszalne, automatyczny powrót                 | E14c, E18                                            | Nie rozpoczęto |
| G12    | E12  | 5/5 zadań w testach użyteczności, E2E, axe, Lighthouse ≥ 90                                                                           | E13, E14a, E15                                       | Nie rozpoczęto |
| G13    | E13  | Dokładnie raz, p95 ≤ 60 s, ochrona przed zalewem                                                                                      | E15                                                  | Nie rozpoczęto |
| G14a   | E14a | Paper = backtest (< 1% różnicy)                                                                                                       | E14b                                                 | Nie rozpoczęto |
| G14b   | E14b | 30 dni testnetu bez rozbieżności, chaos, kill switch ≤ 5 s, bezpieczeństwo kluczy                                                     | E15, E14c                                            | Nie rozpoczęto |
| G15    | E15  | ASVS L2 bez wysokich, NF pod obciążeniem, ćwiczenie DR                                                                                | E16, E14c                                            | Nie rozpoczęto |
| G14c   | E14c | 30 dni zamkniętej bety live bez incydentu krytycznego                                                                                 | Tryby 2–3 bota w E16 (wymaga też G11a)               | Nie rozpoczęto |
| G16    | E16  | 30 dni bety, dostępność ≥ 99,5%, lista gotowości 100%                                                                                 | GA, E17                                              | Nie rozpoczęto |
| G18    | E18  | Odczyt zgodny z eksploratorem na 50 tokenach, ocena skalibrowana, zużycie kredytów RPC < 80%                                          | Udostępnienie skanera publicznie                     | Nie rozpoczęto |

**Dowody zaliczonych bramek:**

| Bramka | Raport             | Plik dowodu                 | Rodzaj dowodu                           |
| ------ | ------------------ | --------------------------- | --------------------------------------- |
| G0     | `docs/gates/G0.md` | `docs/gates/G0.passed.json` | lokalny (komputer i klucze właściciela) |
| G1     | `docs/gates/G1.md` | `docs/gates/G1.passed.json` | CI na `main`, przebieg 45027155138      |
| G2     | `docs/gates/G2.md` | `docs/gates/G2.passed.json` | CI na `main`, przebieg 45144539739      |

### Jak bramki są egzekwowane

1. Każdy PR ma etykietę etapu (`E7` itd.). Workflow `gate-guard.yml` sprawdza, czy bramki wymagane do tego etapu mają plik `docs/gates/G<nr>.passed.json` na `main` (z identyfikatorem przebiegu CI, który je zaliczył). Jeśli nie, PR jest czerwony.
2. Plik `.passed.json` może utworzyć tylko workflow `gate.yml` uruchamiany na `main`; zmiana ręczna jest odrzucana przez regułę CODEOWNERS i sprawdzenie podpisu przebiegu.
3. Zmiana w module objętym zaliczoną bramką uruchamia ponownie testy tej bramki w CI. Regresja = bramka wraca do statusu "Zablokowana" i blokuje PR-y etapów zależnych do czasu naprawy.
4. Wyjątek od bramki wymaga ADR z uzasadnieniem i terminem usunięcia wyjątku.

**Wdrożenie w repozytorium (decyzja z 22.11.2026, jawne odstępstwa od punktów 1–2 i kroku 8 pipeline):**

- Bramka nie ma osobnego workflow `gate.yml`. Job „8 bramka G<nr>” jest częścią `ci.yml` i działa przy **każdym** PR i każdym pushu na `main`, na Linuksie i na macOS. To mocniej niż ręczne uruchomienie: każdy commit na `main` ma przebieg bramki.
- `main` jest chroniony (tylko PR, podpisane commity), więc workflow nie może sam zapisać pliku na `main`. Plik `.passed.json` tworzy właściciel skryptem `scripts/gate_pass.py` i scala go przez PR. Pliku nie da się podrobić: `gate-guard` (`scripts/gate_guard.py`) przy każdym PR pobiera z GitHuba przebieg o podanym ID i odrzuca dowód, jeśli to nie jest zielony `push` na `main` z `ci.yml`, inny commit albo job bramki nie jest zielony. `CODEOWNERS` przypisuje pliki dowodów właścicielowi.
- Plik `.passed.json` może też przygotować asystent tym samym skryptem `gate_pass.py` (tak powstał dowód G2, PR #54); właściciel scala go przez PR, a `gate-guard` sprawdza dowód niezależnie od tego, kto go utworzył.
- Bramka, której wszystkie sprawdzenia działają wyłącznie u właściciela (G0: komputer i klucze z `.env.local`), ma dowód **lokalny**: raport `make gate G=0` z `main` bez FAIL i SKIP. `gate-guard` przyjmuje dowód lokalny tylko dla takiej bramki.
- Bramka, której część dowodów powstaje na prawdziwej infrastrukturze (G3, ADR-0007), ma w `gates/G<nr>.yaml` blok `evidence` i przyjmuje **wyłącznie** dowód **mixed**: przebieg `ci.yml` na `main` (jak typ ci) oraz przebiegi wymienionych workflow (ten plik, dozwolone zdarzenie bez `pull_request`, `main`, sukces przebiegu i joba z reguły, to repozytorium, commit nie starszy niż commit części ci, każdy przebieg tylko raz) i raporty lokalne w `docs/gates/G<nr>/` (suma SHA-256, nagłówek z commitem nie starszym niż część ci, bez linii FAIL, ostatnia linia PASS z czasem w limicie). Reguły czyta `gate-guard` z `main` (`git show`); nazwa joba bramki to zawsze „8 bramka G<nr> (ubuntu-latest)”, nigdy wartość z pliku dowodu (także dla typu ci). Próby obejścia i testy mutacyjne: `scripts/tests/test_gate_guard.py`, niezależna recenzja PR 3 (raport w `docs/gates/G3.md`).
- Wymagane bramki etapów: `gates/requirements.yaml` (z wiersza „Zależności” każdego etapu). PR bez etykiety etapu przechodzi tylko z etykietą `dependencies`.
- `gate-guard` działa na zdarzeniu `pull_request_target`: workflow, skrypt i reguły bramek zawsze pochodzą z `main`, a kod z PR nie jest pobierany ani uruchamiany (tylko uprawnienia do odczytu; test `test_workflow_never_runs_pr_code_with_target_trigger`). Dzięki temu PR nie może podmienić kontroli, której sam podlega (luka z #13, zamknięta w PR #46 i 10b).
- `gate-guard` czyta etykiety PR z API w chwili uruchomienia (nie z ładunku zdarzenia), nie reaguje na `opened` i nie anuluje przebiegów: anulowany przebieg mógł zostać uznany za wynik wymaganego checka i zablokować scalenie (PR #18, 22.11.2026). PR otwarty bez etykiety nie ma checka `gate-guard`, więc ruleset blokuje scalenie do czasu dodania etykiety.

## 4. Pipeline CI/CD

| Krok                            | Wyzwalacz                                         | Zawartość                                                                                                                                                                                      | Czas docelowy         | Przy niepowodzeniu                           |
| ------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- | -------------------------------------------- |
| 1. Lokalnie (pre-commit)        | Każdy commit                                      | ruff, biome, gitleaks, kontrola rozmiaru plików                                                                                                                                                | < 20 s                | Commit zablokowany                           |
| 2. Szybkie CI                   | Każdy push                                        | Lint, typy (pyright, tsc), testy jednostkowe i właściwości, import-linter                                                                                                                      | < 5 min               | Czerwony status                              |
| 3. Pełne CI                     | PR do `main`                                      | Krok 2 + integracyjne (testcontainers), kontraktowe (Schemathesis, JSON Schema), regresja golden files, Vitest, build obrazów arm64 i amd64, Trivy, CodeQL, gitleaks na historii, `gate-guard` | < 15 min              | Merge zablokowany                            |
| 4. Ewaluacja LLM                | PR zmieniający `prompts/` lub konfigurację modeli | Zbiory wzorcowe, porównanie z poprzednią wersją, koszt                                                                                                                                         | < 20 min              | Merge zablokowany                            |
| 5. Wdrożenie staging            | Merge do `main`                                   | Push obrazów do GHCR, podpis cosign, `docker compose pull && up`, migracje, test dymny                                                                                                         | < 10 min              | Automatyczny rollback do poprzedniego obrazu |
| 6. E2E na staging               | Po wdrożeniu                                      | Playwright (3 silniki + mobile), axe, zrzuty wizualne, Lighthouse CI                                                                                                                           | < 15 min              | Alert; blokada promocji na produkcję         |
| 7. Nocne                        | Cron 02:00 UTC                                    | Testy kontraktowe zewnętrznych API na żywo, pełny ZAP baseline, test odtworzenia kopii (tygodniowo), raport dryfu modeli                                                                       | do 1 h                | Zadanie naprawcze na kolejny dzień           |
| 8. Bramka etapu                 | Ręcznie na `main` (`gate.yml`)                    | Testy z `gates/G<nr>.yaml`, raport, plik `.passed.json`                                                                                                                                        | zależnie od bramki    | Bramka niezaliczona; lista braków w raporcie |
| 9. Wdrożenie produkcji (od E16) | Tag wersji + zatwierdzenie w GitHub Environment   | Te same obrazy co staging (bez przebudowy), blue-green, test dymny, monitoring 30 min                                                                                                          | < 15 min + obserwacja | Automatyczny powrót do poprzedniej wersji    |

**Zasada niezmiennych artefaktów:** na produkcję trafia dokładnie ten obraz (ten sam skrót SHA), który przeszedł testy na staging. Konfiguracja różni się tylko zaszyfrowanymi sekretami i zmiennymi środowiska.
