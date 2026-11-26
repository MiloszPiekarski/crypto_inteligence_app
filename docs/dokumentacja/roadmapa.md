# Roadmapa etapów E0–E18

Każdy etap ma tę samą kartę: cel, zależności, czas, koszty, rezultat i bramkę, a pod nią zakres prac, konfigurację z architekturą i przepływem danych oraz tabelę testów. Czasy zakładają pracę jednej osoby równolegle ze studiami.

_(W Claude Docs w tym miejscu jest interaktywna mapa etapów: 5 faz, 18 etapów, bramki między fazami.)_

Fazy nie są wodospadem: w ich obrębie etapy niezależne mogą biec równolegle (np. E6 obok E4–E5, E10 obok E11), ale żaden etap nie startuje przed zaliczeniem bramek, od których zależy.

## Kolejność prac: ścieżka pracy inżynierskiej (od 26.11.2026)

Projekt ma dwie ścieżki realizacji (ADR-0008, `fundamenty.md`, sekcja 0). **Teraz obowiązuje
ścieżka pracy:** etapy z tabeli poniżej w wersji okrojonej do minimum spełniającego zakres
pracy inżynierskiej. Karty etapów niżej nadal opisują pełny produkt; w karcie każdego etapu
ścieżki pracy podsekcja **„Ścieżka pracy inżynierskiej”** mówi, co robimy teraz
(„Zakres w ścieżce pracy”, nadrzędny wobec „Zakresu prac” do czasu powrotu do produktu)
i co przechodzi do produktu („Dokończenie w ścieżce produktu”). Kryteria bramek pracy
`G<nr>p`: `testy.md`, sekcja 3a. Zależności egzekwuje `gate-guard` (`gates/requirements.yaml`).

| Kolejność | Etap | Zależności (ścieżka pracy)                | Minimum w ścieżce pracy                                                                           | Bramka pracy | Status |
| --------- | ---- | ----------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------ | ------ |
| 1         | E4   | G3                                        | 2 giełdy, 20 par, świece 1 h od 2023-01-01, detektor luk, DQ, cena referencyjna                   | G4p          | ⬜     |
| 2         | E5   | G4p                                       | `MarketView(as_of)`, ok. 15–20 cech `fs-1p`, test point-in-time, wartości referencyjne            | G5p          | ⬜     |
| 3         | E6   | G2, G3 (może biec równolegle z E4–E5)     | API tylko do odczytu, bez kont użytkowników                                                       | G6p          | ⬜     |
| 4         | E12a | G2 (może biec równolegle; zalecane po E5) | persony, 4 zadania kluczowe, makiety w Figma Free, mini design system                             | część G12p   | ⬜     |
| 5         | E7   | G5p                                       | agenci Trend, Ryzyko i zmienność, Reżim, Historyczny (kNN); 2 punkty odniesienia; Ledger          | G7p          | ⬜     |
| 6         | E8   | G5p, G7p                                  | LightGBM: kierunek + kwantyle 24 h, walk-forward, uczciwy raport, bez MLOps                       | G8p          | ⬜     |
| 7         | E9   | G7p, G8p                                  | fuzja, ocena ryzyka, komunikaty ostrzegawcze, podpowiedzi z szablonów bez LLM                     | G9p          | ⬜     |
| 8         | E11  | G5p, G9p                                  | silnik backtestu, 3 strategie, metryki (zwrot, Sharpe, maks. obsunięcie, trafność)                | G11p         | ⬜     |
| 9         | E12b | G6p, G9p, G11p                            | panel wyników (wykresy, wskaźniki, agenci, ryzyko, scenariusze ML, ostrzeżenia), test z 3 osobami | G12p         | ⬜     |

**Odłożone do ścieżki produktu (⏸, karty bez zmian):** E10, E10a, E11a, E13, E14 (a–c),
E15, E16, E17, E18, z E0 konto Resend (klucz API i sprawdzenie w E13), a w etapach ścieżki
pracy wszystko z podsekcji „Dokończenie w ścieżce produktu”. Powrót do produktu:
`docs/start-nowej-rozmowy.md`, sekcja „Przełączenie na ścieżkę produktu”.

## E0. Konta, narzędzia i środowisko lokalne

Etap kończy się, gdy wszystkie konta istnieją z 2FA, klucze są w menedżerze haseł, a skrypt `doctor` potwierdza gotowość komputera.

**Stan na 22.11.2026: E0 zakończony, G0 zaliczona.** Dowody: `scripts/doctor.sh` 36/36 PASS (narzędzia, `.env.local` 600 i ignorowany przez git, Anthropic/Gemini/OpenRouter odpowiadają, CoinGecko + OKX/Bybit/Coinbase/Kraken zwracają dane z Polski, Oracle: region eu-amsterdam-1, CLI działa jako użytkownik IAM `terraform` z polityką ograniczoną do compartmentu `goatcash`); przegląd 15 kont (2FA + wpis w Bitwardenie) potwierdzony; zdublowane `uv` usunięte; Oracle Pay As You Go potwierdzone e-mailem 22.11.2026, alarm budżetu 1 USD (alarm, nie twarda blokada). Komputer roboczy to Mac zarządzany przez pracodawcę (decyzja właściciela projektu); połączenie Sentry z Claude jest na prywatnym koncie, do przepięcia w E3/E6.

| Pole       | Treść                                                                                                           |
| ---------- | --------------------------------------------------------------------------------------------------------------- |
| Cel        | Przygotować wszystkie konta i narzędzia, żeby późniejsze etapy nie zatrzymywały się na rejestracjach i limitach |
| Zależności | Brak                                                                                                            |
| Czas       | 2–4 dni                                                                                                         |
| Koszty     | Domena 10–20 USD; reszta 0                                                                                      |
| Rezultat   | Lista kont w menedżerze haseł, działające narzędzia lokalne, skrypt `doctor`                                    |
| Bramka G0  | Wszystkie testy z tabeli poniżej zielone                                                                        |

### Zakres prac

1. Osobny adres e-mail projektu; menedżer haseł (Bitwarden, plan darmowy) z sejfem projektu.
2. GitHub: konto z 2FA (passkey lub klucz sprzętowy); repo projektu na koncie prywatnym: `MiloszPiekarski/crypto_inteligence_app` (decyzja z 21.11.2026, zamiast organizacji i nazwy `platform`).
3. Oracle Cloud: rejestracja, **region domowy w UE** (Frankfurt lub Amsterdam), przejście na Pay As You Go, alarm budżetu 1 USD, użytkownik IAM do Terraform (bez używania konta root).
4. Cloudflare: konto, zakup domeny w Cloudflare Registrar, włączenie R2. Nazwa produktu: **GoatCash**; domena `goatcash.app` kupiona 21.11.2026 na 1 rok z auto-renew (wygasa 21.11.2027), zweryfikowana w rejestrze .app. Nazwę sprawdzono w TMview: brak znaków w klasach 9, 36, 42.
5. Dostawcy AI: Anthropic Console (klucz, limit wydatków 10 USD), Google AI Studio (klucz Gemini), OpenRouter (zapas, limit 5 USD).
6. Dane: klucz CoinGecko Demo.
7. Monitoring i komunikacja: Grafana Cloud, Sentry, Better Stack, Resend, bot Telegram (BotFather).
8. Komputer: Docker (Docker Desktop lub OrbStack; na Windows WSL2), git, gh, uv, Python 3.12, Node 24 LTS, pnpm, Terraform, Ansible, sops, age, pre-commit, VS Code, Claude Code.
9. Skrypt `scripts/doctor.sh` sprawdzający wersje narzędzi i dostęp do usług.

### Konfiguracja, architektura, przepływ danych

Klucze nie trafiają jeszcze nigdzie poza menedżer haseł i lokalny plik `.env.local`. W E1 zostaną zaszyfrowane SOPS. Integracje na tym etapie to wyłącznie testy połączenia.

### Testy

| Co sprawdzamy       | Jak                                                                      | Narzędzie       | Wynik poprawny                               | Przy niepowodzeniu                                     |
| ------------------- | ------------------------------------------------------------------------ | --------------- | -------------------------------------------- | ------------------------------------------------------ |
| Wersje narzędzi     | `scripts/doctor.sh`                                                      | bash            | Wszystkie wersje ≥ minimalnych               | Doinstalować, powtórzyć                                |
| Klucze AI           | Jedno minimalne zapytanie do każdego dostawcy                            | curl w skrypcie | HTTP 200 i odpowiedź modelu                  | Sprawdź limity i region konta                          |
| CoinGecko i giełdy  | Zapytanie o cenę BTC z CoinGecko i świece z OKX, Bybit, Coinbase, Kraken | curl            | 4 giełdy + CoinGecko zwracają dane           | Zanotować blokadę regionu; wybrać inną giełdę przed E4 |
| Oracle              | `oci iam region list` z kluczem użytkownika IAM                          | OCI CLI         | Lista regionów; region domowy w UE           | Poprawić klucz lub polityki IAM                        |
| Bezpieczeństwo kont | Przegląd listy kont                                                      | ręcznie         | Każde konto ma 2FA i wpis w menedżerze haseł | Uzupełnić przed G0                                     |

### Stan realizacji E0 (✅ zrobione z dowodem · ⚠️ brak dowodu w repo, do potwierdzenia)

| Punkt                                                   | Stan          | Dowód                                                                                                                                                                                                                                              |
| ------------------------------------------------------- | ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. E-mail projektu, Bitwarden                           | ✅            | przegląd ręczny 15 kont, `docs/gates/G0.md`                                                                                                                                                                                                        |
| 2. GitHub z 2FA, repo                                   | ✅            | przegląd ręczny; repo `MiloszPiekarski/crypto_inteligence_app` istnieje                                                                                                                                                                            |
| 3. Oracle: region UE, PAYG, alarm 1 USD, użytkownik IAM | ✅            | `doctor.sh`: region eu-amsterdam-1, CLI jako IAM `terraform`; PAYG i budżet `alarm-1usd`: `G0.md` (Uwagi)                                                                                                                                          |
| 4. Cloudflare, domena `goatcash.app`                    | ✅            | domena: opis w punkcie 4 i TMview; R2: dowód z E3 (kopie pgBackRest w R2, `restore-test` 45502801764: 50/50 tabel z R2; tokeny R2 HTTP 200, `docs/gates/G3.md`)                                                                                    |
| 5. Anthropic, Gemini, OpenRouter                        | ✅            | `doctor.sh`: HTTP 200 i odpowiedź modelu; limit OpenRouter 5 USD sprawdzany automatycznie; limit Anthropic 10 USD ustawiony ręcznie w konsoli (bez automatu)                                                                                       |
| 6. CoinGecko Demo                                       | ✅            | `doctor.sh`: cena BTC                                                                                                                                                                                                                              |
| 7. Grafana, Sentry, Better Stack, Resend, Telegram      | ✅ · ⏸ Resend | dowód z E3: Grafana i bot Telegram (`alert-drill` 45494553367, alert doręczony e-mailem i na Telegram), Better Stack (testowy alert 26.11.2026); Sentry na koncie prywatnym (przepięcie: ⏸ produkt); Resend: konto bez klucza API, ⏸ produkt (E13) |
| 8. Narzędzia na komputerze                              | ✅            | `doctor.sh` 36/36 PASS (macOS, 22.11.2026)                                                                                                                                                                                                         |
| 9. `scripts/doctor.sh`                                  | ✅            | plik w repo; uruchamiany przez `make gate G=0`                                                                                                                                                                                                     |

Bramka **G0: zaliczona** · dowód: `docs/gates/G0.md`, `docs/gates/G0.passed.json` (dowód lokalny, patrz zakładka Testy, sekcja 3).

## E1. Repozytorium, standardy, CI i sekrety

Etap kończy się, gdy pusty monorepo przechodzi pełne CI, a próba wypchnięcia fałszywego sekretu jest blokowana na trzech poziomach.

| Pole       | Treść                                                                                                     |
| ---------- | --------------------------------------------------------------------------------------------------------- |
| Cel        | Zbudować "fabrykę": standard kodu, testy i kontrolę bezpieczeństwa, zanim powstanie pierwsza linia logiki |
| Zależności | G0                                                                                                        |
| Czas       | 4–6 dni                                                                                                   |
| Koszty     | 0                                                                                                         |
| Rezultat   | Publiczne repo z szablonem monorepo, CI, ochroną gałęzi, SOPS, ADR-001                                    |
| Bramka G1  | CI zielone na `main`; test wycieku sekretu zablokowany; ADR-001 zatwierdzony                              |

### Zakres prac

1. Repo publiczne `crypto_inteligence_app` ze strukturą z sekcji 8 zakładki Fundamenty (katalog główny pakietu Python nadal `platform/`); README, LICENSE, SECURITY.md (sposób zgłaszania podatności), CONTRIBUTING.md.
2. Python: `uv` workspace, `ruff` (lint + format), `pyright` w trybie strict dla nowych modułów, `pytest`, `pytest-cov`, `hypothesis`, `import-linter`.
3. TypeScript: `pnpm` workspace, Next.js szkielet, Biome (lint + format), Vitest, `tsc --noEmit`.
4. `pre-commit`: ruff, biome, gitleaks, kontrola dużych plików, `check-yaml`, zakaz commitów na `main`.
5. SOPS + age: `infra/secrets/.sops.yaml`, klucze age dla `local`, `staging`, `production`; prywatne w menedżerze haseł.
6. GitHub: ochrona `main` (PR, wymagane checki, podpisane commity, liniowa historia), Secret Scanning + Push Protection, Dependabot, CodeQL, szablony PR i issue, etykiety etapów (`E0`…`E17`).
7. Workflow CI (`ci.yml`): lint → typy → testy jednostkowe → gitleaks → build obrazów → skan Trivy → raport pokrycia.
8. Makefile z komendami `make dev`, `make test`, `make lint`, `make gate G=<nr>`.
9. `docs/adr/` z szablonem; ADR-001: wybór stosu (treść = sekcja 1 Fundamentów).
10. Wybór licencji (rekomendacja AGPL-3.0).

### Architektura i integracje

CI działa na GitHub Actions (darmowe dla repo publicznych). Obrazy budowane dla `linux/arm64` (Oracle A1) i `linux/amd64` (executor na mikro-VM AMD, CI). Rejestr obrazów: GHCR. Skrypt `make gate` uruchamia testy przypisane do bramki i zapisuje wynik jako artefakt.

### Testy

| Co sprawdzamy          | Jak                                                          | Narzędzie                 | Wynik poprawny                          | Przy niepowodzeniu                             |
| ---------------------- | ------------------------------------------------------------ | ------------------------- | --------------------------------------- | ---------------------------------------------- |
| Pipeline CI            | PR z trywialną zmianą                                        | GitHub Actions            | Wszystkie joby zielone w < 10 min       | Naprawić konfigurację przed jakimkolwiek kodem |
| Ochrona przed sekretem | Commit z fałszywym kluczem w formacie AWS                    | gitleaks, push protection | Zablokowane lokalnie, przy pushu i w CI | Poprawić reguły, powtórzyć                     |
| Odszyfrowanie SOPS     | `sops -d` kluczem `local`; próba kluczem z innego środowiska | sops                      | Działa tylko właściwy klucz             | Poprawić `.sops.yaml`                          |
| Ochrona gałęzi         | Próba bezpośredniego pushu na `main`                         | git                       | Odrzucony                               | Poprawić ustawienia repo                       |
| Granice modułów        | Celowy import zabroniony                                     | import-linter             | CI czerwone                             | Poprawić kontrakty import-linter               |
| Obrazy                 | Build obu architektur + skan                                 | Docker Buildx, Trivy      | 0 podatności krytycznych                | Zmienić obraz bazowy lub wersje                |

### Stan realizacji E1 (✅ zrobione z dowodem)

| Punkt                                                                                                | Stan | Dowód                                                                                                                               |
| ---------------------------------------------------------------------------------------------------- | ---- | ----------------------------------------------------------------------------------------------------------------------------------- |
| 1. Repo publiczne, struktura, README, LICENSE, SECURITY.md, CONTRIBUTING.md                          | ✅   | commit `c7e95c1` na `main`; pakiet `goatcash` zamiast `platform` (ADR-0001)                                                         |
| 2. Python: uv, ruff, pyright strict, pytest, pytest-cov, hypothesis, import-linter                   | ✅   | `pyproject.toml`; joby CI 1–3; sondy import-linter w `make gate G=1`                                                                |
| 3. TypeScript: pnpm, Next.js, Biome, Vitest, tsc                                                     | ✅   | `apps/web`, `biome.json`; CI 1–3 (`next build`, Vitest, `tsc --noEmit`)                                                             |
| 4. pre-commit: ruff, biome, gitleaks, duże pliki, check-yaml, zakaz commitów na `main`               | ✅   | `.pre-commit-config.yaml`; test A w `docs/gates/G1.md` (commit z fałszywym kluczem odrzucony lokalnie)                              |
| 5. SOPS + age, klucze local/staging/production                                                       | ✅   | `infra/secrets/.sops.yaml`; sondy SOPS w `make gate G=1` (17/17 u właściciela)                                                      |
| 6. GitHub: ochrona `main`, Secret Scanning + Push Protection, Dependabot, CodeQL, szablony, etykiety | ✅   | krok D sprawdzony przez API; testy A (`GH013`) i B (push na `main` odrzucony) w `G1.md`; etykiety E0–E18 (E18 istnieje w roadmapie) |
| 7. Workflow CI `ci.yml`                                                                              | ✅   | przebieg 45027155138 na `main`: wszystkie joby zielone w 3 min                                                                      |
| 8. Makefile: `make dev`, `make test`, `make lint`, `make gate G=<nr>`                                | ✅   | `Makefile` (także `make audit`, `make tools`)                                                                                       |
| 9. `docs/adr/` + ADR-001                                                                             | ✅   | `docs/adr/0001-wybor-stosu.md`, zatwierdzony scaleniem PR #1                                                                        |
| 10. Licencja                                                                                         | ✅   | AGPL-3.0 (`LICENSE`)                                                                                                                |

Bramka **G1: zaliczona** · dowód: `docs/gates/G1.md`, `docs/gates/G1.passed.json` (przebieg 45027155138, sprawdzany przez `gate-guard`).

**Stan na 22.11.2026: E1 zakończony, G1 zaliczona.** Dowody (szczegóły w `docs/gates/G1.md` w repo): PR #1 scalony (squash, commit `c7e95c1`), co zatwierdza ADR-001; CI na `main` zielone, przebieg 45027155138 (3 min), w tym bramka `make gate G=1` na Linuksie i macOS arm64 (bash 3.2, narzędzia systemowe jak u właściciela); `make gate G=1` u właściciela na `main`: 17 PASS, 0 FAIL, 0 SKIP; sekret zablokowany na 3 poziomach (pre-commit/gitleaks, GitHub Push Protection `GH013`, gitleaks w CI); bezpośredni push na `main` odrzucony; PR z zakazanym importem dał czerwone CI; obrazy platform i executor (arm64 + amd64, Trivy 0 krytycznych) w GHCR. **Jawne rozszerzenia ponad zakres E1** (zapisane w `G1.md`): statyczna kontrola `make audit` (shellcheck, hadolint, actionlint, zizmor), akcje przypięte do SHA, bramka w CI także na macOS, `scripts/sops_check.py` (pliki `*.enc.yaml` muszą być wynikiem `sops -e`), zasady przeglądu w `CONTRIBUTING.md`. Bramki zapisane jako `gates/G<nr>.yaml` zgodnie z zakładką Testy. Do zrobienia przed E2: `gate-guard` i `docs/gates/G1.passed.json` (zakładka Testy, sekcja 8).

## E2. Architektura szczegółowa, model danych i kontrakty

**Status:** ✅ zakończony 23.11.2026, G2 zaliczona (`docs/gates/G2.passed.json`, przebieg 45144539739; raport `docs/gates/G2.md`)

Etap kończy się, gdy model danych, kontrakty API i zdarzeń oraz wymagania niefunkcjonalne są zapisane jako pliki w repo i przechodzą automatyczną walidację. Od tego momentu kod musi być z nimi zgodny.

| Pole       | Treść                                                                                                                                           |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Rozstrzygnąć strukturę danych i interfejsy, zanim zaczniemy je implementować, żeby późniejsze etapy nie zmieniały fundamentów                   |
| Zależności | G1                                                                                                                                              |
| Czas       | 1,5–2 tygodnie                                                                                                                                  |
| Koszty     | 0                                                                                                                                               |
| Rezultat   | ADR-002…006, schemat bazy (migracja Alembic 0001), OpenAPI szkic, JSON Schema zdarzeń, kontrakt `Evidence` v1, wymagania F i NF, model zagrożeń |
| Bramka G2  | Migracja 0001 działa na czystej bazie; schematy przechodzą walidację; wymagania mają identyfikatory i mierzalne kryteria                        |

### Model danych (grupy tabel)

| Grupa         | Tabele                                                                                                                                                                 | Uwagi                                                                                                      |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Rynek         | `assets`, `instruments`, `candles` (hypertable), `candles_ref` (cena referencyjna = mediana giełd), `trades_agg_1m`, `funding_rates`, `open_interest`, `orderbook_top` | Klucz czasowy + `instrument_id`; kolumny `source` i `ingested_at`                                          |
| Jakość danych | `dq_events`, `dq_status`                                                                                                                                               | Każda anomalia danych z typem i decyzją (odrzucono, oznaczono)                                             |
| Cechy         | `feature_sets` (wersje), `feature_values` (hypertable)                                                                                                                 | Wartości zawsze z `as_of` i `data_cutoff`                                                                  |
| Analiza       | `agents`, `evidence`, `assessments`, `narratives`                                                                                                                      | `evidence` przechowuje `p_up`, kwantyle, `facts` (JSONB), `invalidation`, `status`, wersje agenta i modelu |
| Rozliczanie   | `forecast_outcomes`, `agent_metrics_daily`, `fusion_weights`                                                                                                           | Wyniki prognoz i metryki per agent, reżim, horyzont                                                        |
| Teksty        | `news_items`, `news_events`, `embeddings` (pgvector)                                                                                                                   | Deduplikacja po hashu treści                                                                               |
| Użytkownicy   | tabele Better Auth (`user`, `session`, `account`, `verification`), `profiles`, `roles`, `watchlists`                                                                   | Role: `user`, `pro_tester`, `admin`                                                                        |
| Alerty        | `alert_rules`, `alert_events`, `notification_channels`, `deliveries`                                                                                                   | Idempotencja dostarczeń                                                                                    |
| Backtesty     | `strategies`, `backtests`, `backtest_results`                                                                                                                          | Wynik zawiera hash danych i wersję kodu                                                                    |
| Bot           | `exchange_connections`, `bot_configs`, `order_intents`, `orders`, `fills`, `positions`, `bot_events`, `kill_switches`                                                  | Osobny schemat `bot`; dostęp tylko executora i API z ograniczonymi uprawnieniami                           |
| Audyt         | `audit_log`                                                                                                                                                            | Zapisy wyłącznie do dopisywania (append-only)                                                              |

### Kontrakty

- **API:** OpenAPI 3.1 generowane z FastAPI; klient TypeScript generowany automatycznie do `packages/contracts`. Wersjonowanie `/v1`.
- **Zdarzenia (Valkey Streams):** `candle.closed`, `features.ready`, `evidence.published`, `assessment.updated`, `narrative.ready`, `alert.triggered`, `order_intent.created`, `order.updated`. Każde ma JSON Schema z polem `schema_version`.
- **`Evidence` v1:** pola z planu ogólnego (agent, wersje, aktyw, `as_of`, horyzont, `p_up`, kwantyle, `regime_view`, `facts`, `invalidation`, `status`).

### Wymagania niefunkcjonalne (wyciąg)

| ID    | Wymaganie                                                          | Mierzenie                      |
| ----- | ------------------------------------------------------------------ | ------------------------------ |
| NF-01 | Świeżość analizy 1 h: ≤ 3 min po zamknięciu świecy dla 95% aktywów | Metryka `analysis_lag_seconds` |
| NF-02 | API: p95 ≤ 300 ms dla odczytów z cache, ≤ 1 s bez cache            | k6, Grafana                    |
| NF-03 | Dostępność: 99,5% w becie, 99,9% po GA                             | Better Stack                   |
| NF-04 | Kopie: RPO 24 h w budowie, 1 h po GA; RTO 4 h                      | Ćwiczenie odtworzenia w E15    |
| NF-05 | Bezpieczeństwo: zgodność z OWASP ASVS poziom 2 dla API i frontu    | Lista kontrolna w E15          |
| NF-06 | Dostępność UI: WCAG 2.2 AA                                         | axe w Playwright               |
| NF-07 | Bot: od decyzji do zlecenia ≤ 5 s; uzgadnianie stanu co 15 s       | Metryki executora              |

### Pozostałe dokumenty etapu

1. ADR-002 model danych, ADR-003 magistrala zdarzeń (Valkey Streams), ADR-004 uwierzytelnianie, ADR-005 bramka LLM, ADR-006 izolacja executora.
2. Lista wymagań funkcjonalnych z ID (F-xx) przypisanych do etapów.
3. Model zagrożeń STRIDE dla API, executora i panelu administratora.
4. Diagram C4 (kontekst, kontenery) w `docs/`.

### Testy

| Co sprawdzamy       | Jak                                                                                      | Narzędzie               | Wynik poprawny                                 | Przy niepowodzeniu    |
| ------------------- | ---------------------------------------------------------------------------------------- | ----------------------- | ---------------------------------------------- | --------------------- |
| Migracja            | `alembic upgrade head` i `downgrade base` na czystym Postgresie z Timescale w kontenerze | pytest + testcontainers | Obie operacje bez błędów; hypertable utworzone | Poprawić migrację     |
| Schematy zdarzeń    | Walidacja przykładowych komunikatów poprawnych i błędnych                                | jsonschema w pytest     | Poprawne przechodzą, błędne są odrzucane       | Poprawić schematy     |
| OpenAPI             | Lint specyfikacji                                                                        | Spectral                | 0 błędów                                       | Poprawić specyfikację |
| Kompletność wymagań | Skrypt sprawdzający, że każde F-xx ma etap i kryterium                                   | Python                  | 100% wymagań przypisanych                      | Uzupełnić             |

### Stan realizacji E2 (✅ zrobione z dowodem)

| Punkt                                                  | Stan | Dowód                                                                                                     |
| ------------------------------------------------------ | ---- | --------------------------------------------------------------------------------------------------------- |
| 1. ADR-002…006                                         | ✅   | `docs/adr/0002`…`0006`, zatwierdzone scaleniem PR #24; zmiana ADR-0004 (drift Better Auth w E6/G6) PR #27 |
| 2. Schemat bazy (migracja Alembic 0001)                | ✅   | `goatcash.migrations` (0001, 0002 `regime_view`), PR #30 i #34; test `migration` w G2 (29 testów)         |
| 3. JSON Schema zdarzeń (8, z `schema_version`)         | ✅   | `packages/contracts/events/`, PR #32; test `event-schemas` w G2                                           |
| 4. Kontrakt `Evidence` v1                              | ✅   | `packages/contracts/evidence/`, PR #34; test `evidence-v1` w G2                                           |
| 5. Szkic OpenAPI 3.1 (`/v1`) i klient TS               | ✅   | `packages/contracts/openapi/openapi.json`, `goatcash.http_api`, PR #36; Spectral 0 błędów w G2            |
| 6. Wymagania F-xx i NF-xx z etapem i kryterium         | ✅   | `docs/wymagania.yaml` (36 F, 7 NF), PR #40; progi zaakceptowane PR #64 i #68; `make requirements-check`   |
| 7. Model zagrożeń STRIDE (API, executor, panel admina) | ✅   | `docs/architektura/stride.md`, PR #43                                                                     |
| 8. Diagram C4 (kontekst, kontenery)                    | ✅   | `docs/architektura/c4.md` (Mermaid), PR #44; renderowanie na GitHubie potwierdzone przez właściciela      |

Bramka **G2: zaliczona** · dowód: `docs/gates/G2.md`, `docs/gates/G2.passed.json` (przebieg 45144539739, sprawdzany przez `gate-guard`). **Jawne odstępstwa i rozszerzenia** (zapisane w `G2.md`): test migracji w CI tylko na ubuntu (runnery macOS bez Dockera); sprawdzenie rozjazdu schematu Better Auth w E6/G6; `gate-guard` przez `pull_request_target` (PR #46, #48). Do uwzględnienia w E3: obraz platformy bez `alembic.ini` (migracje nie ruszą z obrazu).

## E3. Infrastruktura bazowa

**Status:** ✅ zrobione, bramka G3 zaliczona 25.11.2026 (plan PR-ów i decyzje: `docs/stan-pracy.md`, ADR-0007; raport `docs/gates/G3.md`)

Etap kończy się, gdy środowisko `staging` na Oracle powstaje od zera jedną komendą, ma kopie zapasowe, które faktycznie da się odtworzyć, i wysyła metryki do Grafany.

| Pole       | Treść                                                                                                                                   |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Mieć działającą, odtwarzalną i monitorowaną platformę uruchomieniową dla wszystkich kolejnych etapów                                    |
| Zależności | G2                                                                                                                                      |
| Czas       | 1,5–2 tygodnie                                                                                                                          |
| Koszty     | 0 (Oracle Always Free, Cloudflare Free, Grafana Cloud Free)                                                                             |
| Rezultat   | Terraform + Ansible + Docker Compose; VM A1 i mikro-VM; Postgres/Timescale, Valkey, Caddy, OTel; kopie na R2; DNS i TLS; wdrożenie z CI |
| Bramka G3  | Odtworzenie środowiska od zera < 30 min; test odtworzenia kopii udany; alerty działają                                                  |

### Zakres prac

1. **Terraform (Oracle):** VCN, podsieć publiczna i prywatna, Security Lists (tylko 443 z adresów Cloudflare, 22 z Twojego IP lub przez Tailscale), VM A1 2 OCPU / 12 GB, wolumen 150 GB, mikro-VM AMD z zarezerwowanym IP, OCI Vault (klucz główny dla executora).
2. **Terraform (Cloudflare):** strefa DNS, rekordy `api.` i `app.`, proxy, reguły WAF, limit zapytań, bucket R2, token API o minimalnych uprawnieniach.
3. **Ansible:** użytkownik bez roota, SSH tylko kluczem, fail2ban, automatyczne aktualizacje bezpieczeństwa, Docker, zapora `ufw`, Tailscale do dostępu administracyjnego, swap, limity journald.
4. **Docker Compose `staging`:** `postgres` (obraz TimescaleDB, PG 17, z pgvector), `valkey` (AOF włączony), `caddy` (TLS przez Cloudflare Origin CA), `otel-collector`, `node-exporter`, `postgres-exporter`.
5. **Kopie:** `pgBackRest` – pełna kopia tygodniowo, przyrostowa codziennie, WAL ciągły do R2; szyfrowanie kopii; retencja 30 dni.
6. **Obserwowalność:** OTel → Grafana Cloud (metryki, logi, śledzenie); pulpity: serwer, Postgres, Valkey; alerty (dysk > 80%, brak kopii > 26 h, CPU > 90% przez 15 min) na e-mail i Telegram. Better Stack sprawdza `/health` co minutę.
7. **Wdrożenie:** workflow `deploy-staging.yml`: po zielonym CI na `main` buduje obrazy, wysyła do GHCR, przez SSH (Tailscale) wykonuje `docker compose pull && up -d`, uruchamia migracje i test dymny.
8. **Runbook** `docs/runbooks/` dla: odtworzenia z kopii, rotacji sekretów, wymiany serwera.

### Przepływ danych i integracje

Internet → Cloudflare (WAF, cache) → Caddy na VM → kontenery aplikacji. Baza i Valkey nasłuchują tylko w sieci Dockera. Kopie WAL i pełne trafiają z VM do R2. Telemetria trafia z kolektora OTel do Grafana Cloud. Executor na mikro-VM łączy się z bazą przez Tailscale, nie przez internet.

### Testy

| Co sprawdzamy        | Jak                                                                                | Narzędzie                        | Wynik poprawny                                         | Przy niepowodzeniu                           |
| -------------------- | ---------------------------------------------------------------------------------- | -------------------------------- | ------------------------------------------------------ | -------------------------------------------- |
| Odtwarzalność        | Zniszczenie i odtworzenie staging od zera                                          | terraform destroy/apply, ansible | Działające środowisko w < 30 min, bez ręcznych kroków  | Uzupełnić IaC o brakujący krok               |
| Kopia i odtworzenie  | Zapis danych testowych, kopia, odtworzenie na nowej VM, porównanie sum kontrolnych | pgBackRest, skrypt               | Dane identyczne; odtworzenie do punktu w czasie działa | Etap nie jest ukończony do skutku            |
| Bezpieczeństwo sieci | Skan portów z zewnątrz; próba połączenia z bazą z internetu                        | nmap                             | Otwarty tylko 443 przez Cloudflare                     | Poprawić Security Lists i ufw                |
| Konfiguracja serwera | Audyt hardeningu                                                                   | Lynis                            | Brak ostrzeżeń krytycznych                             | Poprawić role Ansible                        |
| Alerty               | Sztuczne zapełnienie dysku, zatrzymanie kontenera                                  | ręcznie                          | Powiadomienie w < 5 min                                | Poprawić reguły alertów                      |
| Wdrożenie            | Commit na `main`                                                                   | GitHub Actions                   | Nowa wersja na staging; test dymny zielony             | Automatyczny rollback do poprzedniego obrazu |

### Stan realizacji E3 (✅ zrobione z dowodem)

| Punkt                                                                                               | Stan | Dowód                                                                                                                                                                                                                                                                                                                                       |
| --------------------------------------------------------------------------------------------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Terraform Oracle (sieć, A1 2/12, mikro-VM, wolumen, Vault)                                       | ✅   | `infra/terraform/oci`, `oci-trwale`, PR #86, #90; utworzone przez właściciela; wolumen 100 GB zamiast 150 GB (D2, ADR-0007)                                                                                                                                                                                                                 |
| 2. Terraform Cloudflare (DNS, proxy, WAF, limit, R2, Origin CA)                                     | ✅   | `infra/terraform/cloudflare`, PR #90, #92; `external-scan`: 443 tylko przez Cloudflare                                                                                                                                                                                                                                                      |
| 3. Ansible (użytkownik, SSH kluczem, fail2ban, ufw, Docker, Tailscale, swap, journald)              | ✅   | `infra/ansible`, PR #90, #94, #96, #113, #114, #117; `make ansible-test` w G3; `external-scan` 45733147740 po odbudowie: 0 otwartych portów, Lynis 0 warnings na obu serwerach                                                                                                                                                              |
| 4. Docker Compose staging (Postgres 17 + Timescale + pgvector, Valkey AOF, Caddy, OTel, eksportery) | ✅   | `infra/compose/staging`, PR #90; `make compose-staging-test` w G3                                                                                                                                                                                                                                                                           |
| 5. Kopie pgBackRest (pełna, przyrostowa, WAL do R2, szyfrowanie, 30 dni)                            | ✅   | timery systemd (metryka kopii przyrostowej 25.11.2026 02:30 UTC), `backup-now.yml` (PR #98); `restore-test` 45502801764: 50/50 tabel, PITR; retencja 30 dni: konfiguracja, metryka najstarszej kopii i alert > 39 dni (#119); **⏳ samo usunięcie kopii starszej niż 30 dni możliwe najwcześniej ok. 25.12.2026, wtedy sprawdzamy metrykę** |
| 6. Obserwowalność (OTel → Grafana Cloud, pulpity, alerty e-mail i Telegram, Better Stack)           | ✅   | `infra/terraform/observability`, PR #90, #96, #119; metryki i alerty: `alert-drill` 45494553367 (138 s); logi: #115, Loki 5643 linie w 30 min; ślady: #121, Tempo 26.11.2026: 50 śladów `goatcash-api` w 30 min; Better Stack: testowy alert z konsoli dotarł e-mailem (26.11.2026)                                                         |
| 7. Wdrożenie `deploy-staging.yml` (cosign, migracje, test dymny, rollback)                          | ✅   | PR #90, #105; `deploy` 45489734491; rollback i odtworzenie pustej bazy w `make compose-staging-test`                                                                                                                                                                                                                                        |
| 8. Runbooki (odtworzenie z kopii, rotacja sekretów, wymiana serwera)                                | ✅   | `docs/runbooks/`; wymiana serwera sprawdzona w praktyce: `scripts/g3_rebuild.sh`, 1388 s                                                                                                                                                                                                                                                    |

Bramka **G3: zaliczona** · dowód: `docs/gates/G3.md`, `docs/gates/G3.passed.json` (typ mixed: CI 45489734328 i przebiegi deploy, restore-test, external-scan, alert-drill oraz raport lokalny `docs/gates/G3/rebuild-20261125T105824Z.log`, sprawdzane przez `gate-guard`). **Jawne odstępstwa** (zapisane w `G3.md` i ADR-0007 pkt 6): wolumen 100 GB; Better Stack co 3 min (co minutę Grafana Synthetic Monitoring); ćwiczenie alertów workflow zamiast ręcznie; Molecule zastąpione `make ansible-test` (#113); duży PR zamiast PR 7–18; test kopii w CI na `posix` zamiast MinIO; ACL Tailscale w konsoli z kopią w repo; polityka IAM executora przeniesiona do E14b; pakiety apt bez przypięcia (klucze repozytoriów przypięte odciskiem). **Rozliczenie E3 (25–26.11.2026):** braki i naprawy w `G3.md`, sekcja „Rozliczenie E3”.

## E4. Pozyskiwanie danych rynkowych i normalizacja

**Status:** ⬜ nie rozpoczęto · ścieżka pracy: zakres okrojony, bramka G4p (pełny zakres: ⏸ produkt)

Etap kończy się, gdy dla 150 par z czterech giełd dane płyną na żywo, historia jest uzupełniona, a kontrola jakości wykrywa celowo wstrzyknięte błędy.

| Pole       | Treść                                                                                                                                       |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Zapewnić kompletne, sprawdzone i znormalizowane dane, na których oprze się cała analiza                                                     |
| Zależności | G3                                                                                                                                          |
| Czas       | 3 tygodnie                                                                                                                                  |
| Koszty     | 0 (publiczne API, CoinGecko Demo, DefiLlama, RSS)                                                                                           |
| Rezultat   | Moduł `marketdata` z adapterami, proces `ingest`, zadania uzupełniania historii, Data Quality Sentinel, cena referencyjna, zbieranie newsów |
| Bramka G4  | Kompletność ≥ 99,9% świec 1 h za 30 dni; DQ wykrywa ≥ 95% wstrzykniętych błędów; 72 h ciągłej pracy bez interwencji                         |

### Ścieżka pracy inżynierskiej (bramka G4p, ADR-0008)

**Zakres w ścieżce pracy** (obowiązuje teraz; numery punktów odnoszą się do „Zakresu prac” poniżej):

1. Interfejs `MarketDataSource` z punktu 1 (w ścieżce pracy zaimplementowane `instruments()`
   i `candles(range)`; pozostałe metody zadeklarowane, implementacja w produkcie) i dwa adaptery
   przez ccxt: giełda główna i druga, wybrane z OKX, Bybit, Coinbase, Kraken. Na początku etapu
   sprawdzamy dostęp z serwera staging (Amsterdam) i z GitHub Actions; wybór i powód w raporcie G4p.
2. Normalizacja jak w punkcie 2 (symbole `BTC-USDT`, UTC w milisekundach, `Decimal`, precyzja).
3. Uniwersum: stała lista 20 par obecnych na obu giełdach (plik konfiguracyjny), metadane
   z CoinGecko Demo.
4. Świece 1 h przez REST: uzupełnianie historii od 2023-01-01 z punktami kontrolnymi (wznawialne,
   w limitach zapytań giełdy), potem pobieranie co godzinę na staging (proces `ingest`).
5. Detektor luk: oczekiwane vs obecne świece; każda luka sklasyfikowana jako „po stronie
   giełdy” (giełda nie udostępnia świecy, potwierdzone ponownym zapytaniem) albo „nasza”
   (zlecone uzupełnienie); zapis w `dq_events`.
6. Data Quality: reguły z punktu 8 (OHLC spójne, wolumen ≥ 0, brak duplikatów, odchylenie
   od drugiej giełdy > 3%, skok ceny > 8 odchyleń standardowych, brak nowej świecy 1 h dłużej
   niż 2 h); wynik `dq_status` per aktyw i giełda.
7. Cena referencyjna `candles_ref`: mediana źródeł z poprawnym statusem DQ (przy dwóch
   źródłach średnia; gdy jedno ma zły status, drugie z adnotacją).
8. Zdarzenie `candle.closed` w Valkey Streams po zapisie świecy (kontrakt z E2).
9. Workflow raportu danych (uruchamiany na `main`, czyta bazę staging): kompletność względem
   świec udostępnianych przez giełdę i lista luk z klasyfikacją; dowód G4p. Pierwsze
   uruchomienie nowego workflow na serwerze wymaga zgody właściciela (`CLAUDE.md`).

**Dokończenie w ścieżce produktu:** 150 par i 4 giełdy z cotygodniowym doborem uniwersum (top 150 na ≥ 2 giełdach);
websockety świec 1 min i transakcji (`trades_agg_1m`), funding i OI co 5 min, order book
top 20 co 1 min; agregaty ciągłe 5 min–1 d; historia 1 h i 1 d od 2019 oraz 1 min za 2 lata
dla top 30; dane dodatkowe (DefiLlama, Fear & Greed, RSS, FRED); wspólny token bucket
w Valkey z metrykami 429; wykrywanie zawieszonego strumienia; testy: 500 świec vs ponowne
pobranie, agregaty vs giełda, Toxiproxy, 72 h na staging, codzienny test kontraktowy API
giełd. Pełna bramka G4.

### Zakres prac

1. **Interfejs `MarketDataSource`** (metody: `instruments()`, `candles(range)`, `stream_candles()`, `funding()`, `open_interest()`, `orderbook_top()`), implementacje dla OKX, Bybit, Coinbase, Kraken przez ccxt.
2. **Normalizacja:** jednolite symbole (`BTC-USDT`), czas UTC w milisekundach, typ `Decimal` dla cen, mapowanie interwałów, precyzja instrumentów.
3. **Uniwersum aktywów:** zadanie tygodniowe wybiera top 150 par obecnych na ≥ 2 giełdach; metadane z CoinGecko.
4. **Ingest na żywo:** websockety świec 1 min i transakcji (agregowanych do `trades_agg_1m`: wolumen kupna i sprzedaży); funding i OI co 5 min; order book top 20 co 1 min dla top 30 par. Automatyczne ponowne łączenie, heartbeat, wykrywanie zawieszonego strumienia.
5. **Agregacja interwałów:** 5 min, 15 min, 1 h, 4 h, 1 d jako continuous aggregates TimescaleDB z świec 1 min.
6. **Uzupełnianie historii:** zadania z punktami kontrolnymi (wznawialne), respektujące limity zapytań; 1 h i 1 d od 2019, 1 min za 2 lata dla top 30.
7. **Detektor luk:** co godzinę porównuje oczekiwane i obecne świece, zleca uzupełnienie.
8. **Data Quality Sentinel:** reguły (OHLC spójne, wolumen ≥ 0, brak duplikatów), odchylenie od mediany innych giełd > 3%, skok ceny > 8 odchyleń standardowych, nieaktualny strumień > 3 min. Wynik: `dq_status` per aktyw i giełda.
9. **Cena referencyjna:** mediana giełd z poprawnym statusem DQ → `candles_ref`.
10. **Dane dodatkowe:** DefiLlama (dziennie), Fear & Greed (dziennie), RSS (co 5 min, deduplikacja po hashu), FRED (dziennie).
11. **Limity zapytań:** wspólny token bucket per źródło w Valkey; metryki 429 i czas odpowiedzi.

### Przepływ danych

Giełda (websocket/REST) → adapter → normalizacja → walidacja DQ → zapis w `candles` (z `source`) → agregaty ciągłe → `candles_ref` → zdarzenie `candle.closed` w strumieniu Valkey (konsumowane od E5). Odrzucone rekordy trafiają do `dq_events` z przyczyną.

### Testy

| Co sprawdzamy                      | Jak                                                                     | Narzędzie           | Wynik poprawny                                  | Przy niepowodzeniu                                   |
| ---------------------------------- | ----------------------------------------------------------------------- | ------------------- | ----------------------------------------------- | ---------------------------------------------------- |
| Normalizacja                       | Nagrane odpowiedzi giełd (fixtures) → porównanie z oczekiwanym wynikiem | pytest, vcrpy       | 100% zgodności pól i typów                      | Poprawić adapter                                     |
| Reguły DQ                          | Wstrzyknięcie 200 błędów różnych typów do danych testowych              | pytest + Hypothesis | Wykrycie ≥ 95%, fałszywe alarmy < 1%            | Dostroić reguły                                      |
| Poprawność danych vs źródło        | Losowe 500 świec z bazy porównane z ponownym pobraniem z giełdy         | skrypt              | Identyczne OHLCV                                | Diagnoza: strefa czasowa, agregacja, zaokrąglenie    |
| Agregaty                           | Świece 1 h z agregatu vs świece 1 h z giełdy                            | pytest              | Różnica close = 0, wolumen < 0,5%               | Poprawić definicję agregatu                          |
| Odporność                          | Zerwanie websocketu, odpowiedź 429, przerwa sieci 10 min                | Toxiproxy           | Wznowienie bez utraty danych (luki uzupełnione) | Poprawić obsługę błędów                              |
| Integracja na żywo                 | 72 h pracy na staging                                                   | Grafana             | Brak luk niewyjaśnionych; lag ≤ 60 s            | Nie przechodzimy do E5                               |
| Testy kontraktowe zewnętrznych API | Codzienny test schematu odpowiedzi każdej giełdy                        | pytest w CI (cron)  | Schemat bez zmian                               | Alert; adapter aktualizowany przed kolejnym wydaniem |

## E5. Magazyn danych i point-in-time feature store

**Status:** ⬜ nie rozpoczęto · ścieżka pracy: zakres okrojony, bramka G5p (pełny zakres: ⏸ produkt)

Etap kończy się, gdy ta sama biblioteka cech daje bit w bit identyczne wyniki na żywo i przy odtwarzaniu historii, a test "brak zaglądania w przyszłość" przechodzi dla wszystkich cech.

| Pole       | Treść                                                                                                                                     |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Zbudować jedno, wiarygodne źródło cech dla agentów, ML i backtestów, wykluczające wyciek informacji z przyszłości                         |
| Zależności | G4                                                                                                                                        |
| Czas       | 2–2,5 tygodnia                                                                                                                            |
| Koszty     | 0                                                                                                                                         |
| Rezultat   | Moduł `features` (ok. 60 cech w wersji `fs-1`), zadanie liczenia po `candle.closed`, eksport Parquet na R2, polityki retencji i kompresji |
| Bramka G5  | 100% cech przechodzi test point-in-time; zgodność live vs replay; wartości referencyjne wskaźników zgodne z niezależną implementacją      |

### Ścieżka pracy inżynierskiej (bramka G5p, ADR-0008)

**Zakres w ścieżce pracy** (obowiązuje teraz; numery punktów odnoszą się do „Zakresu prac” poniżej):

1. `MarketView(as_of)` dokładnie jak w punkcie 1 (jedyny dostęp agentów i cech do danych;
   `time < as_of`, w replay także `ingested_at ≤ as_of`).
2. Cechy `fs-1p` (ok. 15–20) ze świec 1 h `candles_ref`: zwroty log (1, 4, 24, 168 h),
   zmienność zrealizowana i Parkinsona, ATR, RSI, MACD, ADX, EMA i ich nachylenie, wstęgi
   Bollingera, z-score ceny, Donchian, wolumen względny, korelacja z BTC.
3. Implementacja w Polars z deklaracją okna i źródeł (punkt 3); wersjonowanie `feature_sets`
   z hashem definicji (punkt 4).
4. Zapis `feature_values`; zadanie liczenia po `candle.closed` i pełne przeliczenie historii
   jako zadanie wsadowe; zdarzenie `features.ready` (punkt 7).
5. Braki danych: cecha = `NaN` + status, nigdy cicha interpolacja.
6. Wzory, okna i ograniczenia cech w `docs/praca/metody.md` (przy domknięciu etapu).

**Dokończenie w ścieżce produktu:** pozostałe cechy do ok. 60 w `fs-1` (nierównowaga kupna i sprzedaży, funding i jego
z-score, zmiana OI, rozpiętość i głębokość order booku, dominacja BTC, Fear & Greed, TVL;
wymagają danych z pełnego E4); eksport miesięczny Parquet na R2 (DuckDB); retencja
i kompresja; testy: live vs replay przez 7 dni, wydajność 150 par ≤ 60 s, eksport.
Pełna bramka G5.

### Zakres prac

1. **Kontekst `MarketView(as_of)`:** jedyny sposób dostępu agentów i cech do danych; zwraca wyłącznie dane z `time < as_of` i z `ingested_at ≤ as_of` w trybie replay.
2. **Cechy `fs-1`:** zwroty log (1, 4, 24, 168 h), zmienność zrealizowana i Parkinsona, ATR, RSI, MACD, ADX, EMA i ich nachylenie, wstęgi Bollingera, z-score ceny, Donchian, wolumen względny, nierównowaga kupna/sprzedaży, funding i jego z-score, zmiana OI, rozpiętość i głębokość order booku, korelacja z BTC, dominacja BTC, Fear & Greed, TVL (dla tokenów DeFi).
3. **Implementacja w Polars** (wektorowo); każda cecha deklaruje wymagane okno historii i źródła.
4. **Wersjonowanie:** `feature_sets` z hashem definicji; zmiana definicji = nowa wersja, stare wartości zostają.
5. **Zapis:** `feature_values` (hypertable, kompresja po 7 dniach); eksport miesięczny Parquet na R2 do treningów (DuckDB czyta bezpośrednio).
6. **Retencja:** 1 min surowe 2 lata, potem tylko agregaty; transakcje zagregowane 1 rok; order book top 90 dni.
7. **Zadanie liczenia cech** reaguje na `candle.closed`, publikuje `features.ready`; pełne przeliczenie historii jako zadanie wsadowe.

### Przepływ danych

`candle.closed` → worker buduje `MarketView(as_of)` → liczy cechy → `feature_values` → `features.ready` (konsumowane przez agentów w E7). Co miesiąc: `feature_values` → Parquet na R2 → trening w E8 i backtest w E11.

### Testy

| Co sprawdzamy                | Jak                                                                                           | Narzędzie           | Wynik poprawny                                   | Przy niepowodzeniu                        |
| ---------------------------- | --------------------------------------------------------------------------------------------- | ------------------- | ------------------------------------------------ | ----------------------------------------- |
| Brak zaglądania w przyszłość | Dla 1000 losowych chwil t: cechy z danych obciętych do t vs cechy z pełnych danych w chwili t | pytest + Hypothesis | Identyczne wartości                              | Blokada etapu; poprawić cechę             |
| Poprawność wskaźników        | Porównanie z niezależną implementacją (TA-Lib) i ręcznie policzonymi przykładami              | pytest              | Różnica < 1e-9 (po okresie rozgrzewki)           | Poprawić implementację                    |
| Live vs replay               | 7 dni na żywo vs odtworzenie tych dni z historii                                              | skrypt porównawczy  | Identyczne wartości                              | Szukać różnic w czasie dostępności danych |
| Braki danych                 | Wejście z lukami i statusem DQ = zły                                                          | pytest              | Cecha = `NaN` + status, nigdy cicha interpolacja | Poprawić obsługę braków                   |
| Wydajność                    | Przeliczenie cech dla 150 par po zamknięciu świecy 1 h                                        | pytest-benchmark    | ≤ 60 s na A1                                     | Optymalizacja zapytań, cache okien        |
| Eksport                      | Odczyt Parquet z R2 w DuckDB i porównanie z bazą                                              | skrypt              | Identyczna liczba wierszy i suma kontrolna       | Poprawić eksport                          |

## E6. Backend API, użytkownicy, konta i uprawnienia

**Status:** ⬜ nie rozpoczęto · ścieżka pracy: zakres okrojony, bramka G6p (pełny zakres: ⏸ produkt)

Etap kończy się, gdy użytkownik może założyć konto, włączyć 2FA i pobrać dane rynkowe przez API z kontrolą uprawnień i limitów, a testy kontraktowe potwierdzają zgodność z OpenAPI.

| Pole       | Treść                                                                                                                                                                |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Dostarczyć bezpieczny szkielet API i system kont, na którym oprą się frontend, alerty i bot                                                                          |
| Zależności | G2, G3 (może biec równolegle z E4–E5 po G3)                                                                                                                          |
| Czas       | 2–2,5 tygodnia                                                                                                                                                       |
| Koszty     | 0 (Resend w planie darmowym)                                                                                                                                         |
| Rezultat   | Proces `api`; endpointy rynkowe; Better Auth w Next.js (e-mail + hasło, Google OAuth, TOTP, passkeys); JWT/JWKS; role; limity; audyt; panel administratora (minimum) |
| Bramka G6  | Testy kontraktowe i bezpieczeństwa zielone; brak dostępu do cudzych danych w testach IDOR                                                                            |

### Ścieżka pracy inżynierskiej (bramka G6p, ADR-0008)

**Zakres w ścieżce pracy** (obowiązuje teraz; numery punktów odnoszą się do „Zakresu prac” poniżej):

1. FastAPI jak w punkcie 1: routery per moduł, błędy RFC 9457, paginacja kursorowa, `/v1`,
   nagłówki bezpieczeństwa, CORS tylko dla `app.goatcash.app`.
2. Endpointy tylko do odczytu: `GET /v1/assets`, `/v1/assets/{id}`, `/v1/candles`,
   `/v1/market/overview` (bez WebSocket). Kolejne etapy dokładają swoje endpointy odczytu
   (E7 dowody i agenci, E9 oceny, E11 backtest).
3. Cache odpowiedzi w Valkey z TTL dopasowanym do interwału i unieważnianiem po
   `candle.closed` (punkt 8).
4. Specyfikacja OpenAPI i klient TypeScript w `packages/contracts` zgodne z kodem.

W ścieżce pracy nie ma kont, logowania ani danych użytkowników.

**Dokończenie w ścieżce produktu:** Better Auth (e-mail i hasło, Google OAuth, TOTP, passkeys), JWT/JWKS, role
i `require_owner`, limity sliding window z nagłówkami `RateLimit-*`, profil, zgody i RODO,
audyt, panel administratora, WebSocket `/v1/stream`; testy: autoryzacja, IDOR, przepływy
kont w Playwright, k6, OWASP ZAP, schemat Better Auth. Pełna bramka G6.

### Zakres prac

1. **FastAPI:** struktura routerów per moduł, obsługa błędów w formacie RFC 9457 (Problem Details), paginacja kursorowa, wersja `/v1`, nagłówki bezpieczeństwa, CORS tylko dla domeny aplikacji.
2. **Endpointy rynkowe:** `GET /v1/assets`, `/v1/assets/{id}`, `/v1/candles`, `/v1/market/overview`, WebSocket `/v1/stream` (subskrypcja świec i ocen).
3. **Uwierzytelnianie:** Better Auth w `apps/web` z tabelami w Postgresie; wydaje JWT (EdDSA) z krótkim czasem życia; FastAPI weryfikuje podpis przez JWKS z cache. Weryfikacja e-mail, reset hasła, TOTP, passkeys, wylogowanie ze wszystkich sesji.
4. **Uprawnienia:** role (`user`, `pro_tester`, `admin`) + sprawdzanie własności zasobu w każdym zapytaniu (zależność FastAPI `require_owner`).
5. **Limity:** algorytm sliding window w Valkey per użytkownik i per IP; osobne limity dla czatu LLM i backtestów; nagłówki `RateLimit-*`.
6. **Profil:** język, strefa czasowa, profil ryzyka (kwestionariusz w E12), zgody, eksport i usunięcie konta (RODO).
7. **Audyt:** logowanie, zmiana hasła, 2FA, zmiany uprawnień i każda akcja bota do `audit_log`.
8. **Cache:** odpowiedzi rynkowe w Valkey z TTL dopasowanym do interwału; unieważnianie po `candle.closed`.
9. **Panel administratora (API):** lista użytkowników, blokada konta, globalny kill switch bota, podgląd statusu DQ.

### Przepływ danych i integracje

Przeglądarka → Cloudflare → Next.js (sesja Better Auth, ciasteczko HttpOnly) → JWT → FastAPI → Postgres/Valkey. E-mail przez Resend. Logowanie Google przez OAuth 2.0. Wszystkie odpowiedzi API mają schemat z OpenAPI, z którego frontend generuje klienta.

### Testy

| Co sprawdzamy       | Jak                                                                             | Narzędzie                    | Wynik poprawny                                        | Przy niepowodzeniu                    |
| ------------------- | ------------------------------------------------------------------------------- | ---------------------------- | ----------------------------------------------------- | ------------------------------------- |
| Zgodność z OpenAPI  | Generowanie tysięcy zapytań ze specyfikacji                                     | Schemathesis                 | 0 odpowiedzi niezgodnych ze schematem, 0 błędów 500   | Poprawić endpoint lub specyfikację    |
| Autoryzacja         | Każdy endpoint wywołany bez tokena, z wygasłym, z podrobionym, z cudzym zasobem | pytest (parametryzowane)     | 401 lub 403 we wszystkich przypadkach                 | Blokada G6                            |
| IDOR                | Użytkownik A próbuje odczytać i zmienić zasoby B                                | pytest                       | 0 sukcesów                                            | Blokada G6                            |
| Przepływy kont      | Rejestracja, weryfikacja, 2FA, reset, passkey                                   | Playwright (minimalny UI)    | Wszystkie przechodzą                                  | Poprawić konfigurację Better Auth     |
| Limity              | Seria zapytań ponad limit                                                       | k6                           | 429 po przekroczeniu, poprawne nagłówki               | Poprawić limiter                      |
| Skan bezpieczeństwa | Skan aktywny staging                                                            | OWASP ZAP (baseline)         | 0 alertów wysokich                                    | Poprawić i powtórzyć                  |
| Migracje            | Migracja w górę i w dół z danymi                                                | pytest + testcontainers      | Bez utraty danych                                     | Poprawić migrację                     |
| Schemat Better Auth | `getMigrations()` Better Auth na bazie po `alembic upgrade head` (ADR-0004)     | Better Auth + testcontainers | Pusty wynik: brak tabel, kolumn i indeksów do dodania | Migracja Alembic dopasowująca schemat |

## E7. Agenci analityczni rdzenia, tablica dowodów i Forecast Ledger

**Status:** ⬜ nie rozpoczęto · ścieżka pracy: zakres okrojony, bramka G7p (pełny zakres: ⏸ produkt)

Etap kończy się, gdy siedmiu agentów regułowo-statystycznych publikuje dowody dla 150 par po każdej świecy, a Ledger automatycznie rozlicza ich prognozy i liczy metryki względem punktów odniesienia.

| Pole       | Treść                                                                                                                                                                                  |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Zbudować mechanizm agentów i ich rozliczania; to rdzeń naukowy i produktowy platformy                                                                                                  |
| Zależności | G5                                                                                                                                                                                     |
| Czas       | 4 tygodnie                                                                                                                                                                             |
| Koszty     | 0                                                                                                                                                                                      |
| Rezultat   | Moduły `agents` i `ledger`; agenci: Data Quality (z E4 jako agent), Regime (HMM), Trend, Mean Reversion, Volatility & Risk (GARCH), Levels, Derivatives; punkty odniesienia; Evaluator |
| Bramka G7  | Każdy agent ma testy właściwości; 14 dni dowodów na staging bez luk; Ledger zgadza się z ręcznym przeliczeniem                                                                         |

### Ścieżka pracy inżynierskiej (bramka G7p, ADR-0008)

**Zakres w ścieżce pracy** (obowiązuje teraz; numery punktów odnoszą się do „Zakresu prac” poniżej):

1. Klasa bazowa `Agent` i rejestr w YAML, dostęp tylko przez `MarketView` (punkt 1);
   tablica dowodów z idempotencją i zdarzeniem `evidence.published` (punkt 2).
2. Czterech agentów, horyzont 24 h:
   - _Trend:_ EMA (z nachyleniem) i ADX → `p_up` przez kalibrowaną regresję logistyczną
     na historii;
   - _Ryzyko i zmienność:_ GARCH(1,1) i EWMA → kwantyle zwrotu, VaR 95%, CVaR;
   - _Reżim:_ HMM z 4–5 stanami na zwrotach i zmienności, etykiety stanów po średniej
     i wariancji, filtr online;
   - _Historyczny_ (analiza historycznych danych rynkowych, agent dodany w ścieżce pracy):
     k najbliższych sąsiadów w przestrzeni znormalizowanych cech `fs-1p`, wyłącznie sytuacje
     zakończone przed `as_of` (odstęp równy horyzontowi); `p_up` i kwantyle z rozkładu
     zwrotów po analogiach, liczba analogii i ich daty w `facts`.
3. Punkty odniesienia `baseline_50` i `baseline_freq` (punkt 4).
4. Forecast Ledger i Evaluator (punkt 5): zapis prognozy z hashem przed faktem, rozliczenie
   po upływie horyzontu, Brier, log-loss, pinball, pokrycie przedziałów, ECE per agent ×
   reżim × horyzont.
5. Endpointy odczytu: `/v1/assets/{id}/evidence`, `/v1/agents`, `/v1/agents/{name}/metrics`.
6. Kalibracja wstępna agentów walk-forward na historii od 2023 (parametry zapisane w repo
   albo w artefakcie z hashem danych; bez MLflow).

**Dokończenie w ścieżce produktu:** agenci Mean Reversion (z procesem Ornsteina-Uhlenbecka), Levels, Derivatives i Data
Quality jako agent; filtr Kalmana, Donchian i momentum w agencie Trend; ryzyko płynności
z order booku; punkty odniesienia `baseline_persistence` i `baseline_vol`; MLflow; pełna
lista agentów z punktu 3; testy: 14 dni dowodów na staging bez luk, wydajność 150 par
≤ 60 s, Kalman i OU na szeregach syntetycznych. Pełna bramka G7.

### Zakres prac

1. **Klasa bazowa `Agent`:** `name`, `version`, `horizons`, `required_features`, metoda `run(view: MarketView) -> Evidence`; rejestr agentów z konfiguracją w YAML; agent nie ma dostępu do bazy poza `MarketView`.
2. **Tablica dowodów:** zapis `evidence` + publikacja `evidence.published`; idempotencja po (agent, wersja, aktyw, `as_of`, horyzont).
3. **Agenci:**
   - _Regime:_ HMM z 4–5 stanami na zwrotach i zmienności; etykiety stanów nadawane po średniej i wariancji; filtr online.
   - _Trend:_ EMA, ADX, Donchian, momentum szeregów czasowych → `p_up` przez kalibrowaną regresję logistyczną na historii.
   - _Mean Reversion:_ z-score, RSI, Bollinger, warunkowo od reżimu.
   - _Volatility & Risk:_ GARCH(1,1) i EWMA → kwantyle zwrotu, VaR 95%, CVaR, ryzyko płynności z order booku.
   - _Levels:_ profil wolumenu, punkty zwrotne, skupiska płynności → poziomy z siłą i historią reakcji.
   - _Derivatives:_ funding, zmiana OI, przegrzanie rynku.
4. **Punkty odniesienia jako agenci:** `baseline_50` (stałe 50%), `baseline_freq` (historyczna częstość wzrostów), `baseline_persistence` (kierunek jak ostatnio), `baseline_vol` (kwantyle z historycznej zmienności).
5. **Forecast Ledger:** zapis prognozy z hashem treści przed faktem; Evaluator uruchamiany przez `scheduler` po upływie horyzontu; metryki Brier, log-loss, pinball, pokrycie przedziałów, kalibracja (ECE) per agent × reżim × horyzont × dzień.
6. **Endpointy:** `GET /v1/assets/{id}/evidence`, `/v1/agents`, `/v1/agents/{name}/metrics`.
7. **Kalibracja wstępna** każdego agenta na historii 2019–2024 (walk-forward), z zapisem parametrów w MLflow.

**Modele ilościowe w agentach (uzupełnienie):**

- _Filtr Kalmana jako uczciwa wartość:_ agent Trend utrzymuje dynamiczną ocenę "uczciwej" ceny i jej niepewności. Wzmocnienie K = P⁻ / (P⁻ + R) określa, jak mocno nowa obserwacja zmienia ocenę. Odchylenie ceny od uczciwej wartości w jednostkach niepewności trafia do `facts`.
- _Proces Ornsteina-Uhlenbecka w Mean Reversion:_ estymacja szybkości powrotu κ i półokresu ln 2 / κ z regresji AR(1) na odchyleniu od uczciwej wartości. Agent prognozuje powrót tylko wtedy, gdy półokres jest krótszy od horyzontu, a κ jest istotne statystycznie.
- _Wpływ sprzedaży w Volatility & Risk:_ dla puli o stałym iloczynie spadek ceny = 1 − (R / (R + q))². Dla giełd z order bookiem odpowiednikiem jest głębokość order booku: ile procent ceny kosztuje sprzedaż 1% dziennego wolumenu.

### Przepływ danych

`features.ready` → orkiestrator w workerze uruchamia agentów w kolejności zależności (DQ → Regime → pozostali równolegle) → `evidence` + `evidence.published` → (E9: fuzja). Co godzinę Evaluator: `evidence` z upływającym horyzontem + `candles_ref` → `forecast_outcomes` → `agent_metrics_daily`.

### Testy

| Co sprawdzamy                          | Jak                                                            | Narzędzie            | Wynik poprawny                                                                                             | Przy niepowodzeniu                                              |
| -------------------------------------- | -------------------------------------------------------------- | -------------------- | ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Logika agentów na danych syntetycznych | Idealny trend wzrostowy, spadkowy, szum, skok zmienności       | pytest + Hypothesis  | Trend: `p_up` > 0,5 w trendzie wzrostowym; Regime rozpoznaje skok zmienności; Volatility zwiększa kwantyle | Poprawić agenta                                                 |
| Kontrakt `Evidence`                    | Walidacja każdego wyniku schematem                             | Pydantic, jsonschema | 100% zgodnych                                                                                              | Blokada publikacji dowodu                                       |
| Point-in-time                          | Agent uruchomiony w replay na danych obciętych do t vs pełnych | pytest               | Identyczne dowody                                                                                          | Blokada G7                                                      |
| Poprawność Ledgera                     | 200 ręcznie przeliczonych prognoz (arkusz referencyjny)        | pytest               | Metryki identyczne do 1e-12                                                                                | Poprawić Evaluator                                              |
| Kalibracja                             | Wykres kalibracji walk-forward                                 | MLflow, raport       | ECE ≤ 0,05 dla agentów z `p_up`                                                                            | Ponowna kalibracja lub oznaczenie agenta jako eksperymentalnego |
| Porównanie z punktami odniesienia      | Brier agenta vs `baseline_freq`                                | raport tygodniowy    | Wynik raportowany niezależnie od znaku; agent gorszy od punktu odniesienia ma wagę 0 w fuzji               | Decyzja w E9, nie blokuje G7                                    |
| Wydajność                              | Wszyscy agenci dla 150 par                                     | benchmark            | ≤ 60 s po `features.ready`                                                                                 | Optymalizacja, więcej workerów                                  |
| Kalman i Ornstein-Uhlenbeck            | Szereg syntetyczny ze znaną uczciwą wartością i znanym κ       | pytest + Hypothesis  | Estymowane κ w przedziale ±10% od prawdziwego; filtr zbiega do uczciwej wartości                           | Poprawić estymator                                              |

## E8. Modele ML: trening, walidacja, rejestr i MLOps

**Status:** ⬜ nie rozpoczęto · ścieżka pracy: zakres okrojony, bramka G8p (pełny zakres: ⏸ produkt)

Etap kończy się, gdy ML Forecaster i Anomaly Agent są trenowane automatycznie co tydzień, promowane wyłącznie przez bramkę champion/challenger, a każdy wynik da się odtworzyć z MLflow.

| Pole       | Treść                                                                                                                                                                   |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Dodać uczone modele prognozujące oraz proces, który utrzymuje ich jakość w czasie                                                                                       |
| Zależności | G5, G7 (kontrakt i Ledger)                                                                                                                                              |
| Czas       | 3–3,5 tygodnia                                                                                                                                                          |
| Koszty     | 0 (trening na CPU A1 w nocy)                                                                                                                                            |
| Rezultat   | MLflow (śledzenie + rejestr, artefakty na R2), pipeline treningowy, ML Forecaster (LightGBM, kierunek + kwantyle dla 4 h / 24 h / 7 d), Anomaly Agent, monitoring dryfu |
| Bramka G8  | Odtwarzalność treningu; brak wycieku w walidacji; raport walk-forward z punktami odniesienia; działający tryb cienia                                                    |

### Ścieżka pracy inżynierskiej (bramka G8p, ADR-0008)

**Zakres w ścieżce pracy** (obowiązuje teraz; numery punktów odnoszą się do „Zakresu prac” poniżej):

1. Etykiety jak w punkcie 1, jeden horyzont: 24 h.
2. Zbiór treningowy z `feature_values` (`fs-1p`), z bazy albo lokalnego pliku Parquet
   (bez R2), z zapisanym hashem zbioru.
3. Walidacja jak w punkcie 3: walk-forward z oknem rozszerzającym, purging równy horyzontowi,
   embargo 1%, zbiór zamknięty = ostatnie 6 miesięcy.
4. Model kierunku: LightGBM + kalibracja izotoniczna (punkt 4); model kwantyli q10, q50, q90
   z korektą conformal (punkt 5).
5. Hiperparametry: mała stała siatka, wybór na walidacji, nigdy na zbiorze zamkniętym.
6. Agent `ml_forecaster` publikujący `Evidence` (`p_up` i kwantyle 24 h) z modelu zapisanego
   jako artefakt z hashem danych, seedem i commitem; trening uruchamiany skryptem.
7. Raport walk-forward względem punktów odniesienia i agentów z E7, wynik raportowany
   uczciwie także bez przewagi (`docs/praca/`).

**Dokończenie w ścieżce produktu:** horyzonty 4 h i 7 d; MLflow (śledzenie, rejestr `challenger`/`champion`, artefakty
na R2, UI przez Tailscale); Optuna (100 prób); SHAP w `facts`; Anomaly Agent; tryb cienia
14 dni i skrypt promocji; monitoring dryfu (PSI); cotygodniowy retrening; testy: promocja,
dryf, wydajność inferencji. Pełna bramka G8.

### Zakres prac

1. **Etykiety:** zwrot logarytmiczny w horyzoncie z `candles_ref`; kierunek (zwrot > 0); dla kwantyli – sam zwrot. Etykieta powstaje dopiero po upływie horyzontu.
2. **Zbiór treningowy:** Parquet z R2 (cechy `fs-1`) → DuckDB → Polars; panel wszystkich aktywów z cechami aktywa i rynku; zapis hasha zbioru.
3. **Walidacja:** walk-forward z oknem rozszerzającym, purging równy horyzontowi i embargo 1%; zbiór zamknięty = ostatnie 6 miesięcy.
4. **Model kierunku:** LightGBM (binarny) + kalibracja izotoniczna na osobnym fragmencie.
5. **Model kwantyli:** LightGBM z funkcją straty kwantylowej (q10, q50, q90) + korekta pokrycia (conformal prediction).
6. **Dobór hiperparametrów:** Optuna z ograniczoną liczbą prób (100), wynik na walidacji, nigdy na zbiorze zamkniętym.
7. **Interpretowalność:** SHAP dla każdej prognozy (top 5 cech trafia do `facts` dowodu).
8. **Anomaly Agent:** Isolation Forest na cechach wolumenu, zmienności i order booku + CUSUM dla nagłych zmian.
9. **MLflow:** eksperymenty, rejestr z etapami `challenger` i `champion`; artefakty na R2; dostęp do UI tylko przez Tailscale.
10. **Tryb cienia i promocja:** challenger publikuje dowody z flagą `shadow` przez 14 dni; skrypt promocji wymaga: lepszy Brier (test Diebolda-Mariano p < 0,05), ECE nie gorsze, pokrycie kwantyli 75–85%.
11. **Monitoring dryfu:** PSI cech tygodniowo; alarm przy PSI > 0,25 dla ważnych cech lub spadku trafności poniżej punktu odniesienia przez 7 dni.
12. **Harmonogram:** retrening w niedzielę w nocy (cron arq), limit CPU dla kontenera treningowego, żeby nie spowalniać analiz.

### Przepływ danych

R2 (Parquet) → trening → MLflow (model + metryki + hash danych + commit) → rejestr `challenger` → worker ładuje model → dowody `shadow` → Ledger → skrypt promocji → `champion` → worker przeładowuje model bez restartu.

### Testy

| Co sprawdzamy                | Jak                                                       | Narzędzie | Wynik poprawny                                  | Przy niepowodzeniu                                           |
| ---------------------------- | --------------------------------------------------------- | --------- | ----------------------------------------------- | ------------------------------------------------------------ |
| Odtwarzalność                | Dwa treningi z tym samym hashem danych i seedem           | pytest    | Identyczne predykcje                            | Usunąć źródła niedeterminizmu                                |
| Wyciek w walidacji           | Test z cechą-pułapką zawierającą przyszły zwrot           | pytest    | Pipeline wykrywa i odrzuca cechę (kontrola dat) | Blokada G8                                                   |
| Sensowność modelu            | Trening na danych z wbudowanym sygnałem vs czystym szumie | pytest    | Na sygnale AUC > 0,6; na szumie AUC ≈ 0,5       | Poprawić pipeline                                            |
| Jakość vs punkty odniesienia | Raport walk-forward                                       | MLflow    | Raport kompletny; wynik raportowany uczciwie    | Brak przewagi nie blokuje G8, ale model nie wchodzi do fuzji |
| Kalibracja i pokrycie        | ECE i pokrycie q10–q90                                    | raport    | ECE ≤ 0,05; pokrycie 75–85%                     | Ponowna kalibracja                                           |
| Promocja                     | Symulacja challengera lepszego i gorszego                 | pytest    | Lepszy promowany, gorszy odrzucony              | Poprawić skrypt                                              |
| Dryf                         | Sztuczne przesunięcie rozkładu cechy                      | pytest    | Alarm PSI                                       | Poprawić monitor                                             |
| Inferencja                   | Opóźnienie dla 150 par × 3 horyzonty                      | benchmark | ≤ 10 s                                          | Optymalizacja                                                |

## E9. Fuzja, Risk Governor i Indeks Gotowości

**Status:** ⬜ nie rozpoczęto · ścieżka pracy: zakres okrojony, bramka G9p (pełny zakres: ⏸ produkt)

Etap kończy się, gdy dla każdego aktywa powstaje jedna skalibrowana ocena z miarą niezgody agentów, Risk Governor poprawnie stosuje weto, a fuzja w walk-forward nie jest gorsza od najlepszego pojedynczego agenta.

| Pole       | Treść                                                                                                                                           |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Połączyć dowody w ocenę, którą można pokazać użytkownikowi i przekazać botowi, z jawnym "nie rób nic"                                           |
| Zależności | G7, G8                                                                                                                                          |
| Czas       | 2,5–3 tygodnie                                                                                                                                  |
| Koszty     | 0                                                                                                                                               |
| Rezultat   | Moduł `fusion`: stacking + wagi multiplikatywne per reżim + kalibracja; Risk Governor z regułami; Indeks Gotowości 0–100; Radar okazji; ablacje |
| Bramka G9  | Brier fuzji ≤ Brier najlepszego agenta (walk-forward); wszystkie reguły weta pokryte testami; raport ablacji                                    |

### Ścieżka pracy inżynierskiej (bramka G9p, ADR-0008)

**Zakres w ścieżce pracy** (obowiązuje teraz; numery punktów odnoszą się do „Zakresu prac” poniżej):

1. Wejście fuzji jak w punkcie 1: `p_up` agentów (bez wag zerowych), reżim, niepewności,
   status DQ.
2. Fuzja: regresja logistyczna na prognozach agentów (walk-forward) + kalibracja izotoniczna.
   Reguła awaryjna: gdy w walk-forward fuzja ma gorszy Brier niż najlepszy agent, ocena łączna
   = najlepszy agent, a raport G9p to opisuje.
3. Niezgoda (entropia i rozrzut `p_up`) i kwantyle ocen (mediana ważona + korekta conformal),
   punkty 4–5.
4. Ocena ryzyka (reguły wersjonowane w YAML; odpowiednik Risk Governora bez bota): zły status
   DQ, reżim paniki, VaR powyżej progu, niezgoda powyżej progu → poziom `niskie`,
   `podwyższone` albo `wysokie` + lista powodów.
5. Komunikaty ostrzegawcze i podpowiedzi z szablonów (bez LLM), wyłącznie opisowe: zakaz
   trybu rozkazującego i słów decyzyjnych („kup”, „sprzedaj”, „wejdź”, „zamknij”),
   sprawdzany testem słownikowym; każda odpowiedź z oceną zawiera informację, że to nie jest
   porada inwestycyjna.
6. Zapis `assessments` + `assessment.updated`; endpoint `/v1/assets/{id}/assessment`,
   `/v1/market/overview` rozszerzony o oceny.

**Dokończenie w ścieżce produktu:** wagi Hedge per reżim, Indeks Gotowości 0–100, Radar okazji (`/v1/radar`,
`/v1/market/readiness`), ablacje i udział Shapleya, weto dla bota (stan `weto`) i reguła
zdarzeń z E10a, 1000 ocen wzorcowych (golden files); warunek „Brier fuzji ≤ najlepszy agent”
jako blokujący. Pełna bramka G9.

### Zakres prac

1. **Wejście fuzji:** wektor `p_up` agentów (bez wag zerowych), reżim, niepewności, status DQ.
2. **Stacking:** regresja logistyczna na prognozach agentów (trenowana walk-forward), osobno per horyzont.
3. **Wagi adaptacyjne:** algorytm Hedge (wagi multiplikatywne) per reżim, aktualizowany przez Evaluator; ostateczna ocena = kalibracja izotoniczna z mieszanki stackingu i Hedge.
4. **Niezgoda:** entropia i rozrzut `p_up` agentów; wysoka niezgoda obniża pewność i jest pokazywana użytkownikowi.
5. **Kwantyle ocen:** mediana ważona kwantyli agentów zmienności i ML + korekta conformal.
6. **Risk Governor (reguły wersjonowane w YAML):** weto przy złym statusie DQ, ekstremalnym reżimie paniki, VaR powyżej progu, niskiej płynności, niezgodzie powyżej progu, anomalii krytycznej. Wynik: `ok`, `ostrożnie`, `weto` + lista powodów.
7. **Indeks Gotowości (0–100):** przewaga (|p\_up − 0,5| po kalibracji) × jakość agentów w bieżącym reżimie × (1 − kara ryzyka) × (1 − kara niezgody); składowe zapisane, żeby UI mogło je wyjaśnić.
8. **Radar okazji:** ranking aktywów po przewadze skorygowanej o ryzyko; aktywa z wetem wykluczone.
9. **Ablacje:** zadanie tygodniowe liczy wynik fuzji bez każdego agenta i udział Shapleya agentów; wynik w `agent_metrics_daily`.
10. **Zapis:** `assessments` + `assessment.updated`; endpointy `/v1/assets/{id}/assessment`, `/v1/radar`, `/v1/market/readiness`.

Od E10a Risk Governor ma dodatkową regułę: niepotwierdzone zdarzenie wysokiej wagi albo potwierdzony hack dotyczący aktywa ustawia status "ostrożnie" i wstrzymuje nowe wejścia bota w tym aktywie do czasu weryfikacji.

### Przepływ danych

`evidence.published` (wszyscy agenci dla aktywa i horyzontu) → fuzja → Risk Governor → `assessments` → `assessment.updated` → Narrator (E10), alerty (E13), bot (E14). Evaluator → `fusion_weights`.

### Testy

| Co sprawdzamy    | Jak                                                                                                      | Narzędzie                | Wynik poprawny                                                      | Przy niepowodzeniu                                 |
| ---------------- | -------------------------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------- | -------------------------------------------------- |
| Matematyka fuzji | Znane wejścia i ręcznie policzone wyjścia                                                                | pytest                   | Zgodność do 1e-9                                                    | Poprawić implementację                             |
| Własności        | Wszyscy agenci zgodni → wynik po tej samej stronie; agent z wagą 0 nie wpływa na wynik; wynik w \[0, 1\] | Hypothesis               | Brak kontrprzykładów                                                | Poprawić logikę                                    |
| Reguły weta      | Tabela przypadków dla każdej reguły i ich kombinacji                                                     | pytest (parametryzowane) | 100% przypadków zgodnych z tabelą decyzji                           | Blokada G9                                         |
| Jakość fuzji     | Walk-forward 2019–2026 bez zbioru zamkniętego                                                            | raport MLflow            | Brier fuzji ≤ najlepszy agent; kalibracja ECE ≤ 0,05                | Uproszczenie fuzji (np. tylko Hedge), ponowny test |
| Odporność        | Brak dowodu jednego agenta, opóźniony dowód, agent zwraca błąd                                           | pytest                   | Ocena powstaje bez niego, z adnotacją; nigdy z nieaktualnym dowodem | Poprawić orkiestrację                              |
| Regresja         | Zapisane 1000 ocen wzorcowych; po zmianie kodu porównanie                                                | pytest (golden files)    | Brak zmian lub zmiany uzasadnione w PR                              | Wyjaśnić różnicę przed merge                       |

## E10. Warstwa LLM: bramka, Narrator, newsy i sentyment, RAG, ewaluacja

**Status:** ⏸ odłożone (produkt): realizacja po obronie pracy (ADR-0008); karta bez zmian

Etap kończy się, gdy narracje i analiza newsów działają dla 150 par, każda liczba w tekście przechodzi walidację względem dowodów, a zmiana promptu lub modelu jest możliwa tylko po przejściu zbioru ewaluacyjnego.

| Pole       | Treść                                                                                                                                                                                                    |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Zamienić ustrukturyzowane wyniki w zrozumiałe wyjaśnienia i wnieść informacje z newsów, bez ryzyka halucynacji                                                                                           |
| Zależności | G9 (narracja), G4 (newsy mogą ruszać od G4 równolegle)                                                                                                                                                   |
| Czas       | 3,5–4 tygodnie                                                                                                                                                                                           |
| Koszty     | Faza budowy 0–5 USD/mies. (darmowy Gemini, minimalne testy Claude)                                                                                                                                       |
| Rezultat   | Moduł `llm` (LiteLLM, aliasy ról, budżety, wyłączniki), Narrator, Adwokat diabła, klasyfikator newsów, ekstrakcja zdarzeń, News & Sentiment Agent, RAG (bge-m3 + pgvector), Langfuse, zbiory ewaluacyjne |
| Bramka G10 | 0 niezgodnych liczb na 500 narracjach; klasyfikator newsów F1 ≥ punkt odniesienia FinBERT + 5 pp.; test awarii dostawców zielony                                                                         |

### Zakres prac

1. **Bramka modeli:** konfiguracja aliasów (`narrator`, `extractor`, `chat`, `deep`, `judge`) w YAML, kolejność zapasowa, timeouty, budżety dzienne w Valkey, wyłącznik obwodu per dostawca.
2. **Prompty:** pliki `prompts/<rola>/vN.yaml` z instrukcją, przykładami i schematem wyjścia; wersja zapisywana przy każdym wyniku.
3. **Narrator:** wejście = ocena + dowody + fakty (bez dostępu do internetu); wyjście JSON (`headline`, `summary`, `drivers[]` z identyfikatorami dowodów, `risks[]`, `invalidation`, `confidence_text`) w PL i EN. Generowanie przez Batch API dla harmonogramu, standardowo na żądanie.
4. **Walidator:** wyciąga wszystkie liczby i nazwy aktywów z tekstu, porównuje z faktami; niezgodność → ponowna generacja (maks. 1) → szablon bez LLM. Lista zakazanych sformułowań (np. gwarancje zysku, "na pewno").
5. **Adwokat diabła:** ten sam zestaw dowodów, zadanie: najmocniejszy kontrargument z odwołaniem do dowodów.
6. **Newsy:** deduplikacja (hash + podobieństwo embeddingów), przypisanie do aktywów (słownik nazw i tickerów + NER), klasyfikator sentymentu lokalny, ekstrakcja zdarzeń przez LLM tylko dla wysokiej istotności.
7. **Zbiór etykiet:** wstępne etykiety LLM, weryfikacja 1500–2000 przykładów w Label Studio, fine-tuning małego enkodera na darmowym GPU, rejestracja w MLflow.
8. **News & Sentiment Agent:** agregaty sentymentu i zdarzeń per aktyw w oknach 4 h / 24 h → `Evidence`; podlega temu samemu Ledgerowi.
9. **RAG:** embeddingi bge-m3 dla newsów, narracji i dokumentacji w pgvector; wyszukiwanie hybrydowe (pełnotekstowe + wektorowe).
10. **Ewaluacja:** zbiory wzorcowe (200 ocen do narracji, 300 nagłówków, 100 pytań czatu); metryki: zgodność liczb, pokrycie kluczowych dowodów, czytelność (ocena modelem innej rodziny + próbka ręczna), długość, koszt.
11. **Langfuse:** śledzenie wywołań, koszt per alias, pseudonimizacja danych użytkowników.

### Przepływ danych

`assessment.updated` → kolejka narracji (priorytet: aktywa oglądane) → bramka LLM → walidator → `narratives` → cache → API. RSS → `news_items` → klasyfikator → (LLM dla ważnych) → `news_events` → News & Sentiment Agent → `evidence`.

### Testy

| Co sprawdzamy         | Jak                                                       | Narzędzie            | Wynik poprawny                                                         | Przy niepowodzeniu                              |
| --------------------- | --------------------------------------------------------- | -------------------- | ---------------------------------------------------------------------- | ----------------------------------------------- |
| Zgodność liczb        | 500 narracji wzorcowych przez walidator                   | pytest               | 0 niezgodności w opublikowanych tekstach                               | Poprawić prompt lub walidator; blokada G10      |
| Schemat wyjścia       | Każda odpowiedź parsowana przez Pydantic                  | pytest               | 100% parsowalnych (po ponowieniu)                                      | Zaostrzyć schemat, wymusić tryb JSON            |
| Jakość narracji       | Zbiór wzorcowy, ocena modelem innej rodziny + 50 ręcznie  | Langfuse datasets    | Średnia ≥ 4/5; brak ocen 1                                             | Iteracja promptu; nowa wersja                   |
| Klasyfikator newsów   | Zbiór testowy 300 nagłówków                               | scikit-learn metrics | Macro F1 ≥ FinBERT + 5 pp.                                             | Więcej danych lub użycie LLM jako klasyfikatora |
| Awaria dostawcy       | Symulacja 500, timeout, 429 u głównego dostawcy           | Toxiproxy, mock      | Przełączenie na zapas; w ostateczności szablon; 0 błędów u użytkownika | Poprawić bramkę                                 |
| Budżety               | Przekroczenie dziennego limitu kosztu                     | pytest               | Przejście na tańszy model lub szablon                                  | Poprawić licznik                                |
| Wstrzykiwanie poleceń | Nagłówki z ukrytymi instrukcjami ("zignoruj poprzednie…") | zbiór testów ataków  | Brak wpływu na wynik; treść zewnętrzna traktowana jako dane            | Wzmocnić separację danych i instrukcji          |
| Regresja promptów     | Każdy PR zmieniający prompt uruchamia ewaluację           | GitHub Actions       | Wynik nie gorszy niż poprzednia wersja                                 | Blokada merge                                   |

## E10a. Agent Zdarzeń (Event Intelligence)

**Status:** ⏸ odłożone (produkt): realizacja po obronie pracy (ADR-0008); karta bez zmian

Etap kończy się, gdy platforma w ciągu kilku minut od pojawienia się istotnego zdarzenia pokazuje:

- co się stało i czy to potwierdzone,
- których kryptowalut to dotyczy,
- jak rynek reagował na podobne zdarzenia w przeszłości,
- jaka część tej reakcji już się dokonała.

Każda taka ocena jest prognozą rozliczaną w Forecast Ledger.

**Założenie projektowe:** pierwsze sekundy po newsie wygrywają boty wysokiej częstotliwości, więc nie konkurujemy szybkością. Nasza przewaga to trafniejsza interpretacja w horyzoncie godzin i dni: weryfikacja, historyczne odpowiedniki, oddzielenie wpływu zdarzenia od ruchu całego rynku i rozpoznanie, czy rynek przereagował.

| Pole        | Treść                                                                                                                                                                                                      |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cel         | Zamieniać wydarzenia ze świata (skandale, hacki, regulacje, listingi, makro) w zweryfikowane, skwantyfikowane i rozliczalne oceny wpływu na kryptowaluty                                                   |
| Zależności  | G10 (bramka LLM, klasyfikator newsów, RAG), G7 (Ledger), G5 (cechy)                                                                                                                                        |
| Czas        | 4 tygodnie + budowa bazy historycznej w tle od E4                                                                                                                                                          |
| Koszty      | Źródła darmowe; LLM ok. 5–15 USD miesięcznie (Claude Haiku 5.5 na zdarzenia wysokiej istotności)                                                                                                           |
| Rezultat    | Moduł `events`: detektor, weryfikator, ekstraktor, mapa powiązań, pamięć zdarzeń z badaniami zdarzeń (event study), model fazy reakcji, kalendarz katalizatorów, karta zdarzenia w UI, alerty w Telegramie |
| Bramka G10a | Weryfikator odrzuca fałszywe zdarzenia z zestawu testowego; event study zgodne z ręcznym przeliczeniem; prognozy reakcji skalibrowane i lepsze od punktu odniesienia albo uczciwie raportowane             |

### Siedem elementów agenta

1. **Detektor zdarzeń:** łączy strumienie newsów, oficjalnych komunikatów i danych on-chain. Zdarzenie powstaje, gdy kilka źródeł mówi o tym samym (klastrowanie embeddingów w oknie 30 min) albo gdy pojawia się komunikat oficjalny.
2. **Weryfikator (ochrona przed fake newsami):** każde zdarzenie ma status _niepotwierdzone_, _potwierdzone_ (≥ 2 niezależne wiarygodne źródła lub źródło oficjalne) albo _zdementowane_. System bierze pod uwagę ranking wiarygodności źródeł, wykrywa przejęte konta (nietypowy styl, link do nowej domeny) i śledzi dementi. Niepotwierdzone zdarzenie o dużej wadze zwiększa ostrożność, ale nie daje sygnału.
3. **Ekstraktor struktury (LLM):** typ według taksonomii (hack lub exploit, listing lub delisting, regulacja lub działanie urzędu, ETF, makro, osoba kluczowa, partnerstwo, odblokowanie podaży, awaria sieci, depeg, upadłość), podmioty, waga, nowość (czy to nowa informacja, czy powtórka). Wynik w ściśle walidowanym JSON.
4. **Mapa powiązań (graf ekspozycji):** podmiot → aktywa z wagą wpływu. Przykłady: firma z sektora AI → tokeny AI; emitent stablecoina → stablecoiny i cały rynek; giełda → jej token; spółka trzymająca BTC w skarbcu → BTC. Wagi startują od ręcznych reguł, a potem są uczone z historycznych współruchów (pętla samouczenia L2).
5. **Pamięć zdarzeń i event study:** baza historycznych zdarzeń 2019–2026 z nadwyżkowymi stopami zwrotu (zwrot aktywa minus zwrot oczekiwany z modelu rynkowego względem BTC i indeksu) po 1 h, 4 h, 24 h i 7 dniach. Dla nowego zdarzenia system znajduje najbliższe odpowiedniki (typ + embedding opisu + reżim rynku) i pokazuje rozkład ich reakcji: mediana, rozrzut, odsetek spadków.
6. **Model fazy reakcji:** rozróżnia szok (pierwsze minuty), przereagowanie i dryf. Dla każdego typu zdarzenia uczy się, czy po szoku dominuje kontynuacja, czy odbicie. Porównuje ruch, który już się dokonał, z typową reakcją odpowiedników (wskaźnik "ile już w cenie").
7. **Kalendarz katalizatorów:** zaplanowane wydarzenia z wyprzedzeniem: decyzje Fed (FOMC), dane CPI, terminy decyzji w sprawie ETF, odblokowania podaży tokenów, aktualizacje sieci, wyniki spółek powiązanych z kryptowalutami. Przed wydarzeniem rozkład historycznych reakcji, po nim porównanie z oczekiwaniem.

**Uzupełnienia agenta:**

- _Uczona wiarygodność źródeł:_ każde źródło ma w Ledgerze historię potwierdzeń i dementi; wiarygodność = rozkład beta aktualizowany po każdym rozstrzygniętym zdarzeniu. Ranking z elementu 2 jest więc wynikiem, a nie ręcznym ustawieniem.
- _Potwierdzenie on-chain:_ napływ tokena na giełdy, ruchy dużych portfeli i zmiany podaży stablecoinów po zdarzeniu zwiększają albo obniżają pewność oceny.
- _Rynki prognoz:_ zmiany szans na Polymarket (tylko odczyt publicznych danych) jako cecha przed zdarzeniami z kalendarza katalizatorów.
- _Zasady wobec osób:_ zdarzenia dotyczące konkretnych ludzi są pokazywane jako kategoria, ze źródłami, dopiero po potwierdzeniu w dwóch wiarygodnych źródłach (zakładka Fundamenty, sekcja 1b).
- _Drzewo eskalacji:_ kolejne możliwe etapy zdarzenia z prawdopodobieństwami z newsów i rynków prognoz (wniosek ze studium Nvidii, Fundamenty, sekcja 1b).
- _Tryb weekendowy:_ luka między perpetualami na akcje i akcjami tokenizowanymi a piątkowym zamknięciem jako sygnał dla poniedziałkowego otwarcia i powiązanych kryptowalut; tylko sygnał do czasu analizy prawnej.
- _Ryzyko kluczowej osoby i zarażenie sektora:_ graf zależności wskazuje, kto traci, a kto zyskuje na kryzysie jednego podmiotu.

### Wynik dla użytkownika: karta zdarzenia

Zweryfikowany status i źródła → które aktywa i jak mocno → rozkład reakcji historycznych odpowiedników → ile reakcji już się dokonało → scenariusz bazowy i alternatywny z warunkiem unieważnienia → ryzyko. Dla zdarzeń negatywnych karta pokazuje scenariusz spadkowy. Zajmowanie pozycji krótkiej (short) wymaga kontraktów perpetual, które bot obsłuży dopiero po GA (backlog E17) z twardym limitem dźwigni.

### Integracje

- **Evidence:** Agent Zdarzeń publikuje dowody jak każdy agent; fuzja daje mu wagę zależną od trafności w Ledgerze.
- **Risk Governor (E9):** niepotwierdzone zdarzenie wysokiej wagi lub hack dotyczący aktywa = status "ostrożnie" i wstrzymanie nowych wejść bota w tym aktywie do czasu weryfikacji.
- **Pętla samouczenia (E11a):** strategie "dryf po zdarzeniu" i "odbicie po przereagowaniu" trafiają do portfela strategii; bandyta uczy się, która działa dla jakiego typu zdarzenia.
- **Alerty (E13):** karta zdarzenia w Telegramie dla aktywów z watchlisty.

### Przepływ danych

Newsy, komunikaty, on-chain → detektor (klastry) → weryfikator → ekstraktor LLM → mapa powiązań → odpowiedniki z pamięci zdarzeń → model fazy reakcji → `Evidence` + karta zdarzenia → fuzja, Risk Governor, alerty. Po upływie horyzontów zdarzenie z rzeczywistą reakcją trafia z powrotem do pamięci zdarzeń.

### Testy

| Co sprawdzamy            | Jak                                                                                             | Narzędzie                | Wynik poprawny                                                                                               | Przy niepowodzeniu                                        |
| ------------------------ | ----------------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------- |
| Weryfikator              | 100 przypadków: prawdziwe zdarzenia, plotki, zdementowane informacje, symulowane przejęte konta | pytest, zbiór wzorcowy   | 0 fałszywych zdarzeń ze statusem "potwierdzone"; ≥ 90% prawdziwych potwierdzonych w ≤ 30 min                 | Blokada G10a                                              |
| Ekstrakcja               | 300 ręcznie opisanych zdarzeń                                                                   | Langfuse datasets        | Typ zgodny ≥ 90%, podmioty ≥ 95%                                                                             | Iteracja promptu lub schematu                             |
| Event study              | 20 zdarzeń przeliczonych ręcznie w arkuszu                                                      | pytest                   | Nadwyżkowe stopy zwrotu zgodne do 1e-9                                                                       | Poprawić obliczenia                                       |
| Wyciek w pamięci zdarzeń | Odpowiedniki szukane w replay tylko wśród zdarzeń sprzed danej chwili                           | pytest                   | Żaden odpowiednik z przyszłości                                                                              | Blokada G10a                                              |
| Jakość prognoz reakcji   | Walk-forward na bazie historycznej                                                              | MLflow                   | Brier lepszy od punktu odniesienia "średni ruch danego typu"; ECE ≤ 0,05                                     | Agent publikuje tylko rozkład odpowiedników, bez kierunku |
| Wstrzykiwanie poleceń    | Teksty newsów z ukrytymi instrukcjami                                                           | zbiór ataków             | Brak wpływu na wynik                                                                                         | Wzmocnić separację                                        |
| Opóźnienie               | Od pojawienia się źródła do karty zdarzenia                                                     | metryki                  | p95 ≤ 5 min dla zdarzeń wysokiej wagi                                                                        | Optymalizacja kolejki                                     |
| Wiarygodność źródeł      | Symulacja źródeł o znanej trafności (90%, 60%, 30%)                                             | pytest                   | Po 100 zdarzeniach kolejność źródeł poprawna, oceny w przedziale ±10 pp.                                     | Poprawić model aktualizacji                               |
| Zasady wobec osób        | 50 zdarzeń dotyczących osób, w tym niepotwierdzone plotki                                       | pytest + przegląd ręczny | 0 kart z niepotwierdzonymi zarzutami; każda karta ma źródła i opis kategorii zamiast szczegółów              | Blokada G10a                                              |
| Tryb weekendowy          | Historyczne weekendy z ważnymi newsami, w tym Nvidia 8.11.2026                                  | pytest + backtest        | Kierunek poniedziałkowego otwarcia trafny w ≥ 60% przypadków; luka liczona bez podglądania przyszłych danych | Tryb wyłączony                                            |

## E11. Backtesting i ocena strategii

**Status:** ⬜ nie rozpoczęto · ścieżka pracy: zakres okrojony, bramka G11p (pełny zakres: ⏸ produkt)

Etap kończy się, gdy silnik backtestów daje wyniki zgodne z ręcznie przeliczonymi strategiami referencyjnymi, uruchamia ten sam kod agentów co produkcja i ostrzega użytkownika przed przeuczeniem.

| Pole       | Treść                                                                                                                                                       |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Pozwolić użytkownikom i nam uczciwie sprawdzać strategie na historii; to też wymagany moduł pracy inżynierskiej                                             |
| Zależności | G5 (dane i cechy), G9 (sygnały fuzji jako blok strategii)                                                                                                   |
| Czas       | 3 tygodnie                                                                                                                                                  |
| Koszty     | 0                                                                                                                                                           |
| Rezultat   | Moduł `backtest` (silnik zdarzeniowy), DSL strategii (JSON Schema), model kosztów, metryki, walk-forward, DSR i PBO, kolejka z limitami, endpointy, raporty |
| Bramka G11 | Zgodność z 5 strategiami referencyjnymi; test braku zaglądania w przyszłość; wydajność w limicie                                                            |

### Ścieżka pracy inżynierskiej (bramka G11p, ADR-0008)

**Zakres w ścieżce pracy** (obowiązuje teraz; numery punktów odnoszą się do „Zakresu prac” poniżej):

1. Silnik zdarzeniowy na `MarketView(as_of)` jak w punkcie 2: decyzja na zamknięciu świecy,
   wykonanie na otwarciu następnej, SL i TP sprawdzane na high/low z konserwatywną kolejnością
   (najpierw strata).
2. Strategie z parametrami: kup i trzymaj, przecięcie EMA (opcjonalnie ze stałym SL i TP),
   sygnał oceny łącznej z E9 z progiem. Konfiguracja jako walidowany JSON (podzbiór DSL
   z punktu 1, bez dowolnego kodu użytkownika).
3. Koszty: prowizja taker giełdy + stały poślizg.
4. Metryki: zwrot całkowity, CAGR, zmienność, Sharpe, Sortino, maks. obsunięcie i czas
   trwania, trafność (win rate), profit factor, ekspozycja, porównanie z kup-i-trzymaj.
5. Endpoint `POST /v1/backtests` synchroniczny, z limitem czasu i zakresu danych; wynik:
   krzywa kapitału, obsunięcia, lista transakcji.

**Dokończenie w ścieżce produktu:** pełny DSL (uniwersum, wyjścia, wielkość pozycji, limity), funding, poślizg zależny
od wolumenu i zmienności, walk-forward strategii, Deflated Sharpe Ratio i PBO (F-36), tryb
wektorowy (vectorbt), kolejka arq z limitami i cache, raport per reżim i CSV,
`/v1/strategies/templates`; testy: 5 strategii referencyjnych (także RSI i rebalans),
wektorowy vs zdarzeniowy, fuzzing DSL. Pełna bramka G11.

### Zakres prac

1. **DSL strategii:** JSON z blokami: uniwersum, sygnał wejścia (wskaźnik, warunek, ocena fuzji, reżim), wyjście (SL, TP, trailing, czas, sygnał przeciwny), wielkość pozycji (stały procent ryzyka, targetowanie zmienności), limity (maks. pozycji, ekspozycja). Walidacja JSON Schema; brak dowolnego kodu użytkownika.
2. **Silnik zdarzeniowy:** iteracja po świecach z `MarketView(as_of)`; decyzja na zamknięciu świecy, wykonanie na otwarciu następnej; SL/TP sprawdzane na high/low z konserwatywną kolejnością (najpierw strata).
3. **Koszty:** prowizje maker/taker per giełda, poślizg zależny od wolumenu względnego i zmienności, funding dla kontraktów perpetual (opcjonalnie).
4. **Metryki:** CAGR, zmienność, Sharpe, Sortino, Calmar, maks. obsunięcie i czas trwania, win rate, profit factor, średni zysk i strata, ekspozycja, obrót, porównanie z kup-i-trzymaj.
5. **Ochrona przed przeuczeniem:** walk-forward; Deflated Sharpe Ratio uwzględniający liczbę prób użytkownika; PBO dla optymalizacji parametrów; ostrzeżenie w UI przy wielu próbach.
6. **Tryb wektorowy** (vectorbt) do szybkich badań wewnętrznych, z testem zgodności wyników z silnikiem zdarzeniowym.
7. **Wykonanie:** kolejka `backtests` w arq, limit 10 dziennie na konto, timeout 5 min, cache wyników identycznych konfiguracji (hash konfiguracji + danych + wersji kodu).
8. **Raport:** krzywa kapitału, obsunięcia, lista transakcji, rozkład zwrotów, wyniki per reżim; eksport CSV.
9. **Endpointy:** `POST /v1/backtests`, `GET /v1/backtests/{id}`, `GET /v1/strategies/templates`.

### Przepływ danych

Użytkownik → API (walidacja DSL, limity) → kolejka → worker: dane z Timescale/Parquet + cechy + historyczne oceny fuzji (z `assessments` lub odtworzone) → silnik → `backtest_results` → powiadomienie przez WebSocket.

### Testy

| Co sprawdzamy                | Jak                                                                                                                    | Narzędzie  | Wynik poprawny                                         | Przy niepowodzeniu                  |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------ | ----------------------------------- |
| Poprawność obliczeń          | 5 strategii referencyjnych (kup i trzymaj, przecięcie EMA, RSI, stały SL/TP, rebalans) przeliczonych ręcznie w arkuszu | pytest     | Identyczne transakcje; kapitał końcowy różnica < 0,01% | Blokada G11                         |
| Metryki                      | Znane serie zwrotów z wynikami z literatury i bibliotek (empyrical)                                                    | pytest     | Zgodność do 1e-6                                       | Poprawić wzór                       |
| Brak zaglądania w przyszłość | Strategia-pułapka używająca przyszłej ceny                                                                             | pytest     | Silnik nie daje do niej dostępu (błąd)                 | Blokada G11                         |
| Kolejność SL/TP              | Świeca dotyka obu poziomów                                                                                             | pytest     | Rozliczony SL                                          | Poprawić regułę                     |
| Wektorowy vs zdarzeniowy     | Te same strategie w obu trybach                                                                                        | pytest     | Różnica wyniku < 0,5%                                  | Wyjaśnić różnicę                    |
| Walidacja DSL                | Fuzzing nieprawidłowych konfiguracji                                                                                   | Hypothesis | Każda odrzucona z czytelnym błędem; 0 błędów 500       | Poprawić schemat                    |
| Wydajność                    | Strategia na 1 aktywie, 1 h, 5 lat                                                                                     | benchmark  | ≤ 10 s                                                 | Optymalizacja pętli (Polars, numba) |

## E11a. Pętla samouczenia: filtr decyzji, dobór strategii, strojenie

**Status:** ⏸ odłożone (produkt): realizacja po obronie pracy (ADR-0008); karta bez zmian

Etap kończy się, gdy system sam uczy się z wyników transakcji z backtestów i paper tradingu, które sygnały realizować, którą strategię wybrać w danym reżimie i jak stroić parametry. Każda zmiana jest wersjonowana, testowana w trybie cienia i odwracalna, a limity ryzyka pozostają poza zasięgiem uczenia (zakładka Fundamenty, sekcja 1a).

| Pole        | Treść                                                                                                                                                                       |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cel         | Zamknąć pętlę samouczenia na decyzjach tradingowych, a nie tylko na prognozach                                                                                              |
| Zależności  | G9, G11. Wyniki paper tradingu z E14a dołączają do pętli, gdy tylko się pojawią                                                                                             |
| Czas        | 3 tygodnie                                                                                                                                                                  |
| Koszty      | 0 (trening na CPU)                                                                                                                                                          |
| Rezultat    | Moduł `learning`: tabela `trade_outcomes`, meta-model, portfel strategii z bandytą, miesięczne strojenie, rejestr polityk `policies`, publiczny panel "Jak system się uczy" |
| Bramka G11a | Brak wycieku w etykietach; filtr poprawia wynik po kosztach albo zostaje wyłączony z uczciwym raportem; granice uczenia nienaruszalne; automatyczny powrót działa           |

### Zakres prac

1. **Zbiór uczący decyzji:** każda transakcja z backtestów walk-forward (E11) i paper tradingu (E14a) trafia do `trade_outcomes` z cechami z chwili sygnału (point-in-time), oceną fuzji, reżimem, niezgodą agentów i płynnością. Etykieta powstaje metodą trzech barier: osiągnięty TP, SL albo limit czasu, wynik liczony po kosztach.
2. **Meta-model (L4):** LightGBM przewiduje prawdopodobieństwo, że transakcja będzie zyskowna po kosztach. Poniżej progu sygnał jest pomijany; powyżej wielkość pozycji rośnie z przewagą (maks. ćwiartka ułamka Kelly'ego i limity użytkownika).
3. **Portfel strategii (L5):** 4–6 strategii zapisanych w DSL z E11: trend, powrót do średniej z procesem Ornsteina-Uhlenbecka, wybicie z konsolidacji, powrót do uczciwej wartości z filtra Kalmana. Kontekstowy bandyta (Thompson sampling) wybiera strategię dla każdego reżimu; eksploracja odbywa się wyłącznie w paper tradingu.
4. **Strojenie (L6):** raz w miesiącu Optuna z celem Deflated Sharpe Ratio na walk-forward; zmiana parametru maks. ±20% na cykl.
5. **Rejestr polityk:** polityka = wersje modeli + meta-model + parametry strategii + stan bandyty. Proces champion/challenger: 14 dni cienia, promocja skryptem z testem istotności, powrót jednym poleceniem.
6. **Strażnik granic:** moduł `learning` ma tylko odczyt konfiguracji ryzyka; kontrakt import-linter i osobny użytkownik bazy bez prawa zapisu do tabel limitów.
7. **Panel "Jak system się uczy":** historia wersji polityk, aktualne wagi agentów, wybory bandyty per reżim, wynik przed i po każdej zmianie.

### Przepływ danych

Backtest i paper → `trade_outcomes` → trening meta-modelu i aktualizacja bandyty (MLflow) → challenger w rejestrze `policies` → 14 dni cienia (decyzje zapisywane, niewykonywane) → skrypt promocji → champion używany przez bota (E14) i przez Radar okazji.

### Testy

| Co sprawdzamy        | Jak                                                              | Narzędzie                 | Wynik poprawny                                                                                          | Przy niepowodzeniu                 |
| -------------------- | ---------------------------------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| Wyciek w etykietach  | Dane syntetyczne ze znanym wynikiem; cecha-pułapka z przyszłości | pytest                    | Etykieta używa tylko danych po wejściu, cechy tylko sprzed; pułapka odrzucona                           | Blokada G11a                       |
| Wartość meta-modelu  | Walk-forward: ta sama strategia z filtrem i bez                  | MLflow, raport            | Sharpe po kosztach wyższy przy nie większym obsunięciu, test istotności p < 0,05                        | Filtr wyłączony, wynik raportowany |
| Bandyta              | Symulacja z kilkoma strategiami o znanej skuteczności            | pytest                    | Po 500 rundach ≥ 80% wyborów najlepszej; skumulowana strata względem optimum rośnie wolniej niż liniowo | Poprawić implementację             |
| Granice uczenia      | Próba zmiany limitu ryzyka z modułu `learning`                   | pytest + uprawnienia bazy | Odmowa i wpis w audycie                                                                                 | Blokada G11a                       |
| Automatyczny powrót  | Wymuszony spadek wyniku aktywnej polityki                        | pytest                    | Powrót do poprzedniej wersji w ≤ 1 cykl i alert                                                         | Poprawić monitor                   |
| Stabilność strojenia | Dwa cykle Optuna na tych samych danych                           | pytest                    | Zmiany w limicie ±20%, wynik powtarzalny                                                                | Poprawić konfigurację              |

## E12. Frontend, UI/UX i design system

**Status:** ⬜ nie rozpoczęto · ścieżka pracy: E12a i E12b w zakresie okrojonym, bramka G12p (pełny zakres: ⏸ produkt)

Etap ma dwie części: projekt (E12a) może zacząć się już po G2, a implementacja (E12b) po G6 i G10. Kończy się, gdy pięć osób bez doświadczenia w tradingu wykonuje kluczowe zadania bez pomocy, a testy E2E, dostępności i wydajności są zielone.

| Pole       | Treść                                                                                                                                                                                 |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Interfejs, który początkującemu odpowiada na pytania z wizji, a zaawansowanemu daje dostęp do dowodów i narzędzi                                                                      |
| Zależności | E12a: G2. E12b: G6, G9, G10, G11 (dla Laboratorium)                                                                                                                                   |
| Czas       | E12a: 2 tygodnie; E12b: 5–6 tygodni                                                                                                                                                   |
| Koszty     | Lovable Pro 1 miesiąc ok. 25 USD; reszta 0                                                                                                                                            |
| Rezultat   | Design system w Figma i w kodzie (tokeny, komponenty shadcn), prototyp Lovable przetestowany z użytkownikami, aplikacja Next.js z widokami poniżej, PL i EN, tryb ciemny i jasny, PWA |
| Bramka G12 | 5/5 uczestników testów wykonuje 4 zadania kluczowe; E2E zielone; axe 0 błędów krytycznych; Lighthouse ≥ 90 (wydajność, dostępność)                                                    |

### Ścieżka pracy inżynierskiej (bramka G12p, ADR-0008)

Zależności w ścieżce pracy: E12a: G2; E12b: G6p, G9p, G11p (bez G10: narracje LLM są w produkcie).

**Zakres w ścieżce pracy, E12a (projekt GUI do pracy):**

1. Persony (początkujący, średniozaawansowany) i 4 zadania kluczowe: „jak wygląda dziś
   rynek?”, „co mówią agenci o tym aktywie i dlaczego?”, „jakie jest ryzyko i jakie są
   scenariusze?”, „jak wypadłaby moja strategia na historii?”.
2. Architektura informacji, makiety niskiej i wysokiej wierności w **Figma Free** (zamiast
   płatnego Lovable); eksport PNG albo PDF w `docs/praca/gui/`.
3. Mini design system: kolory wzrostów i spadków dostępne dla osób z daltonizmem,
   typografia, siatka, komponenty: karta agenta, pasek ryzyka, stożek scenariuszy, wykres
   kalibracji; projekt stanów pustych, ładowania i braku danych.

**Zakres w ścieżce pracy, E12b (panel wyników):**

1. Next.js w `apps/web`, po polsku, jeden motyw; klient API generowany z OpenAPI.
2. Widoki: _Przegląd rynku_ (reżim, 20 par z oceną, poziomem ryzyka i zmianą), _Strona
   aktywa_ (wykres ceny w Lightweight Charts ze wskaźnikami, karty 4 agentów i modelu ML
   z historią trafień z Ledgera, ocena ryzyka z powodami, stożek scenariuszy 24 h w ECharts,
   ostrzeżenia i podpowiedzi), _Laboratorium_ (formularz strategii, wynik backtestu,
   metryki, krzywa kapitału), _Metody i wiarygodność_ (opis metod, kalibracja, Brier
   w czasie, porównanie z punktami odniesienia).
3. Na każdym widoku stała informacja „to nie jest porada inwestycyjna”; jawne stany braku
   danych; atrybucja „Data by CoinGecko” przy danych CoinGecko.
4. Wdrożenie procesu `web` na staging (`app.goatcash.app`).
5. Test sposobu prezentacji wyników z 3 osobami: 4 zadania kluczowe + kwestionariusz SUS,
   raport `docs/praca/test-uzytkownikow.md`.

**Dokończenie w ścieżce produktu:** persona quant; prototyp Lovable i 5 sesji na prototypie;
widoki Pogoda rynkowa z Indeksem Gotowości, Radar okazji, narracje i adwokat diabła, newsy,
Alerty, Zapytaj rynek, Konto, Bot; EN (`next-intl`), tryb jasny i ciemny, PWA; testy:
Playwright w Firefox, WebKit i mobile, regresja wizualna, Lighthouse ≥ 90, 5 sesji
moderowanych na staging. Pełna bramka G12.

### E12a: projekt

1. Persony (początkujący, średniozaawansowany, quant) i 4 zadania kluczowe: "czy dziś działać?", "co jest warte uwagi?", "dlaczego taka ocena?", "jak wypadłaby moja strategia?".
2. Architektura informacji i makiety niskiej wierności w Figma.
3. Design system: kolory (z rozróżnieniem wzrostów i spadków dostępnym dla osób z daltonizmem), typografia, siatka, komponenty: karta dowodu, stożek scenariuszy, wskaźnik gotowości, pasek ryzyka, wykres kalibracji.
4. **Prototyp w Lovable** (przygotuję prompt): klikalna wersja 5 widoków na danych przykładowych; sesje z 5 osobami; lista poprawek.

### E12b: implementacja

| Widok                          | Zawartość                                                                                                                                                                    |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Strona główna (publiczna)      | Opis produktu, Pogoda rynkowa w wersji publicznej, wyniki Ledgera                                                                                                            |
| Pogoda rynkowa                 | Reżim, Indeks Gotowości z wyjaśnieniem składowych, 3 największe zmiany ocen od wczoraj, Radar okazji (top 10)                                                                |
| Strona aktywa (SSR, publiczna) | Wykres ceny z poziomami, stożek scenariuszy 4 h / 24 h / 7 d, narracja, adwokat diabła, karty dowodów z historią trafień agentów, karta ryzyka, warunek unieważnienia, newsy |
| Radar okazji                   | Tabela z filtrami (horyzont, ryzyko, kategoria), sortowanie po przewadze skorygowanej o ryzyko                                                                               |
| Wiarygodność                   | Wykresy kalibracji, Brier w czasie, ranking agentów per reżim, ablacje                                                                                                       |
| Laboratorium                   | Kreator strategii (formularz na DSL), wyniki backtestu, porównanie strategii, ostrzeżenia o przeuczeniu                                                                      |
| Alerty                         | Lista reguł, kanały, historia                                                                                                                                                |
| Zapytaj rynek                  | Czat z odpowiedziami zawierającymi odnośniki do dowodów                                                                                                                      |
| Konto                          | Profil, kwestionariusz ryzyka, język, 2FA, passkeys, sesje, eksport i usunięcie danych                                                                                       |
| Bot                            | Szkielet sekcji (wypełniany w E14)                                                                                                                                           |

Technika: React Server Components dla stron publicznych, TanStack Query dla danych interaktywnych, hook WebSocket z automatycznym wznawianiem, `next-intl` (PL/EN), Lightweight Charts (cena), ECharts (stożki, kalibracja), klient API generowany z OpenAPI, PWA (manifest, service worker, Web Push w E13). Każdy stan pusty, ładowania i braku danych ma osobny projekt, zgodnie z zasadą "brak danych to stan jawny".

Wymóg licencyjny: plan CoinGecko Demo wymaga atrybucji, więc widoki z danymi CoinGecko pokazują dopisek „Data by CoinGecko” z linkiem (test w E12b).

### Testy

| Co sprawdzamy       | Jak                                                                               | Narzędzie                | Wynik poprawny                                         | Przy niepowodzeniu                          |
| ------------------- | --------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------ | ------------------------------------------- |
| Komponenty          | Testy jednostkowe komponentów z danymi brzegowymi (brak danych, wartości skrajne) | Vitest + Testing Library | 100% przechodzi; pokrycie komponentów domenowych ≥ 80% | Poprawić komponent                          |
| Ścieżki użytkownika | 4 zadania kluczowe + rejestracja + backtest                                       | Playwright               | Zielone na Chromium, Firefox, WebKit, mobile           | Blokada G12                                 |
| Regresja wizualna   | Zrzuty ekranów głównych widoków                                                   | Playwright screenshots   | Różnice tylko zatwierdzone w PR                        | Przegląd i aktualizacja wzorca lub poprawka |
| Dostępność          | Skan każdego widoku                                                               | axe-core w Playwright    | 0 naruszeń krytycznych i poważnych                     | Poprawić przed merge                        |
| Wydajność           | Strona aktywa i Pogoda rynkowa                                                    | Lighthouse CI            | ≥ 90; LCP ≤ 2,5 s                                      | Optymalizacja (cache, rozmiar paczki)       |
| Zgodność z API      | Typy klienta generowane z OpenAPI w CI                                            | tsc                      | Zmiana API bez aktualizacji frontu = błąd kompilacji   | Zaktualizować klienta                       |
| Użyteczność         | 5 sesji moderowanych na staging                                                   | ręcznie, nagrania        | 5/5 zadań kluczowych bez pomocy                        | Poprawki i powtórka z nowymi osobami        |

## E13. Alerty, powiadomienia i monitoring rynku

**Status:** ⏸ odłożone (produkt): realizacja po obronie pracy (ADR-0008); karta bez zmian

Etap kończy się, gdy reguły alertów użytkowników są sprawdzane po każdej nowej ocenie, a powiadomienie dociera każdym kanałem dokładnie raz, w ciągu 60 sekund.

| Pole       | Treść                                                                                                                            |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Informować użytkownika o istotnych zmianach bez potrzeby ciągłego sprawdzania aplikacji                                          |
| Zależności | G9 (zdarzenia ocen), G6 (konta), G12 (UI ustawień)                                                                               |
| Czas       | 2 tygodnie                                                                                                                       |
| Koszty     | 0 (Resend Free, Telegram, Web Push)                                                                                              |
| Rezultat   | Moduł `alerts`: reguły, ewaluator, kanały (e-mail, Telegram, Web Push, w aplikacji), ciche godziny, limity, dzienne podsumowanie |
| Bramka G13 | Dostarczenie dokładnie raz; p95 opóźnienia ≤ 60 s; brak spamu przy gwałtownym rynku                                              |

### Zakres prac

1. **Typy reguł:** przekroczenie ceny lub poziomu z Levels Agent, zmiana reżimu, odwrócenie oceny fuzji, Indeks Gotowości powyżej/poniżej progu, wzrost niezgody agentów, anomalia, ważne zdarzenie z newsów dla aktywa z watchlisty, depeg stablecoina.
2. **Ewaluator:** konsumuje `assessment.updated`, `candle.closed`, `news_event`; reguły indeksowane po aktywie, żeby nie sprawdzać wszystkich; histereza (reguła nie odpala ponownie, dopóki warunek nie wróci).
3. **Dostarczanie:** zdarzenie `alert.triggered` → kolejka per kanał → idempotencja po (reguła, zdarzenie) w `deliveries`; ponowienia z backoffem; kanał nieudany 5 razy = wyłączony z informacją.
4. **Kanały:** Telegram jako kanał główny (powiązanie konta jednorazowym kodem, komendy /alerts, /watch, /token, /dev), e-mail (Resend, szablony PL/EN, link wypisania), Web Push (VAPID, service worker z E12), powiadomienia w aplikacji.
5. **Ochrona przed zalewem:** limit alertów na użytkownika na godzinę, grupowanie podobnych, ciche godziny w strefie czasowej użytkownika.
6. **Podsumowanie dzienne:** e-mail lub Telegram z Pogodą rynkową i zmianami na watchliście (opcjonalnie).
7. **Monitoring rynku dla zespołu:** wewnętrzne alerty o anomaliach danych i rynku (krach, zatrzymanie giełdy) do kanału administratora.

### Testy

| Co sprawdzamy | Jak                                                   | Narzędzie                   | Wynik poprawny                                            | Przy niepowodzeniu               |
| ------------- | ----------------------------------------------------- | --------------------------- | --------------------------------------------------------- | -------------------------------- |
| Logika reguł  | Tabela przypadków dla każdego typu reguły z histerezą | pytest                      | 100% zgodnych                                             | Poprawić ewaluator               |
| Dokładnie raz | Podwójne zdarzenie, restart workera w trakcie wysyłki | pytest + testcontainers     | 1 dostarczenie                                            | Poprawić idempotencję            |
| Kanały        | Wysyłka na konta testowe e-mail, Telegram, push       | test integracyjny (staging) | Wiadomość odebrana, poprawna treść i język                | Diagnoza konfiguracji kanału     |
| Opóźnienie    | 1000 reguł, symulowany strumień ocen                  | k6 + metryki                | p95 ≤ 60 s                                                | Optymalizacja indeksowania reguł |
| Zalew         | Symulacja krachu: 150 aktywów zmienia reżim naraz     | pytest                      | Limit i grupowanie działają                               | Poprawić limity                  |
| Awaria kanału | Resend zwraca błędy                                   | mock                        | Ponowienia, potem oznaczenie kanału; inne kanały działają | Poprawić izolację kanałów        |

## E14. Trading Bot

**Status:** ⏸ odłożone (produkt): realizacja po obronie pracy (ADR-0008); karta bez zmian

Bot powstaje w trzech podetapach z osobnymi bramkami, bo każdy kolejny dotyka prawdziwych pieniędzy w większym stopniu. Kończy się, gdy po 30 dniach na testnecie stan zleceń i pozycji nigdy nie rozjechał się z giełdą, a kill switch zatrzymuje wszystko w ≤ 5 s.

| Pole       | Treść                                                                                                                               |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Wykonywać decyzje systemu na koncie użytkownika w wybranym poziomie autonomii, bezpiecznie i audytowalnie                           |
| Zależności | E14a: G9, G11, G12. E14b: G14a, G3 (mikro-VM, Vault). E14c: G14b, G15                                                               |
| Czas       | E14a: 2 tyg.; E14b: 4 tyg. + 30 dni testnetu w tle; E14c: 2 tyg. + 30 dni zamkniętej bety                                           |
| Koszty     | 0 (testnety); w E14c własny mały kapitał testowy, np. 50–100 USD                                                                    |
| Rezultat   | Moduł `bot_core`, proces `executor`, adaptery OKX i Bybit, tryby 0 / 0,5 / 1 / 2 / 3, kill switch, dziennik audytu, sekcja Bot w UI |
| Bramki     | G14a (paper), G14b (testnet), G14c (live z limitami)                                                                                |

### Architektura executora

- **Izolacja:** osobna mikro-VM, osobny obraz, osobny użytkownik bazy z dostępem tylko do schematu `bot`; połączenie z bazą przez Tailscale; jedyny proces, który może odszyfrować klucze (OCI Vault + klucz danych per użytkownik w pamięci, nigdy w logach).
- **Maszyna stanów zlecenia:** `PENDING → SUBMITTED → PARTIALLY_FILLED → FILLED | CANCELED | REJECTED | EXPIRED`; każde przejście zapisane w `bot_events`.
- **Idempotencja:** `clientOrderId` = hash identyfikatora intencji; ponowienie nigdy nie tworzy drugiego zlecenia.
- **SL/TP po stronie giełdy:** składane razem z wejściem (zlecenia warunkowe lub dołączone, zależnie od giełdy), więc chronią pozycję nawet przy awarii serwera.
- **Uzgadnianie stanu co 15 s:** salda, zlecenia otwarte, pozycje z giełdy vs baza; rozbieżność = wstrzymanie bota użytkownika i alert.
- **Silnik ryzyka (w `bot_core`, uruchamiany dwukrotnie: przy tworzeniu intencji i w executorze tuż przed wysłaniem):** ryzyko na transakcję (domyślnie 0,5%, maks. 2%), ekspozycja całkowita, korelacja z otwartymi pozycjami, dzienny limit straty, maks. obsunięcie, seria strat, świeżość danych ≤ 2 min, weto Risk Governora, status DQ, minimalna płynność.
- **Kill switch:** użytkownika (anuluj zlecenia, opcjonalnie zamknij pozycje), globalny administratora, automatyczny (bezpieczniki z silnika ryzyka, błędy giełdy, utrata danych).

### E14a: paper i tryb cienia

1. Polityka użytkownika (DSL z E11 + parametry ryzyka) → intencje zleceń w trybie 0 (propozycje) i 0,5 (wirtualne wykonanie z modelem kosztów z E11).
2. Wirtualny portfel, wyniki vs kup-i-trzymaj, powiadomienia o propozycjach.
3. **G14a:** wyniki paper tradingu zgodne z backtestem tych samych dni (różnica < 1%).

Każda wirtualna transakcja trafia do `trade_outcomes` i zasila pętlę samouczenia z E11a (filtr decyzji, dobór strategii). Eksploracja bandyty odbywa się wyłącznie w trybie paper.

### E14b: integracje giełd i testnet

1. Adaptery OKX (demo przez nagłówek symulacji) i Bybit (testnet) za interfejsem `ExchangeExecution`.
2. Dodawanie klucza: weryfikacja uprawnień przez API giełdy (odrzucenie klucza z prawem wypłat), wymagana biała lista IP executora, test połączenia, szyfrowanie, 2FA przy zapisie.
3. Tryb 1 (zatwierdzanie): powiadomienie z przyciskiem zatwierdzenia, ważność propozycji 5 min.
4. 30 dni pracy na testnecie na kontach testowych z trybów 1–3.
5. **G14b:** 0 rozbieżności stanu niewyjaśnionych; wszystkie testy chaosu zielone.

### E14c: live z limitami

1. Tryby 2 i 3 tylko spot, bez dźwigni; twarde limity globalne (maks. kapitał pod zarządzaniem bota na użytkownika w becie, np. 500 USD).
2. Warunki włączenia: 14 dni w trybie cienia dla trybu 2, 30 dni w trybie 1 lub 2 dla trybu 3; test wiedzy o ryzyku; 2FA.
3. Zamknięta beta z własnym kontem i kilkoma zaproszonymi osobami.
4. **G14c:** 30 dni bez incydentu krytycznego; każda transakcja odtwarzalna z dziennika audytu.

Tryby 2 i 3 korzystają wyłącznie z polityki w statusie champion z rejestru E11a. Dlatego E14c wymaga także zaliczonej bramki G11a.

### Testy

| Co sprawdzamy              | Jak                                                                                                        | Narzędzie                 | Wynik poprawny                                           | Przy niepowodzeniu                        |
| -------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------- | -------------------------------------------------------- | ----------------------------------------- |
| Silnik ryzyka              | Losowe kombinacje portfeli, sygnałów i limitów                                                             | Hypothesis                | Żadna przepuszczona intencja nie narusza limitu          | Blokada wszystkich bramek E14             |
| Maszyna stanów             | Wszystkie przejścia, w tym niedozwolone                                                                    | pytest                    | Niedozwolone odrzucone i zalogowane                      | Poprawić                                  |
| Idempotencja               | Podwójne wysłanie tej samej intencji, restart w trakcie                                                    | testnet                   | Jedno zlecenie                                           | Blokada G14b                              |
| Częściowe wypełnienia      | Zlecenia limit na mało płynnych parach testnetu                                                            | testnet                   | Poprawna pozycja i SL dopasowany do wypełnionej ilości   | Poprawić obsługę                          |
| Chaos                      | Utrata sieci 2 min, restart executora z otwartymi pozycjami, 429, przesunięcie zegara, odrzucenie zlecenia | Toxiproxy, testnet        | Stan uzgodniony po powrocie; SL na giełdzie nienaruszony | Blokada G14b                              |
| Kill switch                | Wyzwolenie przy 20 otwartych zleceniach                                                                    | testnet + stoper w teście | Wszystkie anulowane w ≤ 5 s                              | Optymalizacja ścieżki anulowania          |
| Bezpieczeństwo kluczy      | Próba odczytu kluczy z API, logów, zrzutu pamięci workera                                                  | test penetracyjny         | Brak dostępu poza executorem                             | Blokada G14b                              |
| Uprawnienia klucza         | Dodanie klucza z prawem wypłat                                                                             | test integracyjny         | Odrzucony z komunikatem                                  | Poprawić walidację                        |
| Zgodność paper vs backtest | Te same dni i strategia                                                                                    | skrypt                    | Różnica < 1%                                             | Szukać rozbieżności w kosztach lub czasie |

## E15. Bezpieczeństwo, wydajność i odporność

**Status:** ⏸ odłożone (produkt): realizacja po obronie pracy (ADR-0008); karta bez zmian

Etap kończy się, gdy platforma przechodzi audyt według OWASP ASVS poziom 2, wytrzymuje dziesięciokrotność zakładanego ruchu beta, a ćwiczenie awarii z pełnym odtworzeniem mieści się w RTO 4 h. Bez G15 nie ma publicznego startu ani bota na żywych środkach.

| Pole       | Treść                                                                                                                                                      |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Zweryfikować całość tak, jak zrobiłby to atakujący, duży ruch i awaria dostawcy                                                                            |
| Zależności | G12, G13, G14b                                                                                                                                             |
| Czas       | 2–3 tygodnie                                                                                                                                               |
| Koszty     | 0 (narzędzia open source); opcjonalnie program bug bounty bez nagród pieniężnych                                                                           |
| Rezultat   | Raport audytu ASVS, raport testów obciążeniowych, raport ćwiczenia DR, poprawki, runbooki incydentów, polityka prywatności i regulamin (wersja techniczna) |
| Bramka G15 | 0 podatności wysokich i krytycznych otwartych; NF-01…NF-07 spełnione pod obciążeniem; ćwiczenie DR udane                                                   |

### Zakres prac

1. **Przegląd ASVS L2:** uwierzytelnianie, sesje, kontrola dostępu, walidacja wejść, kryptografia, logowanie, konfiguracja; lista kontrolna w repo.
2. **Testy penetracyjne własne:** OWASP ZAP (pełny skan), testy IDOR i eskalacji uprawnień, CSRF, XSS w narracjach i newsach (treść z LLM i z zewnątrz zawsze sanitizowana), SSRF w adapterach, nagłówki bezpieczeństwa (CSP, HSTS).
3. **Łańcuch dostaw:** SBOM (Syft), skan obrazów i zależności (Trivy, Dependabot), przypięte wersje akcji GitHub, podpisywanie obrazów (cosign).
4. **Testy obciążeniowe (k6):** profil beta ×10: 500 równoczesnych użytkowników, 2000 połączeń WebSocket, 50 backtestów w kolejce, 150 par × pełny cykl analizy; test wytrzymałościowy 24 h.
5. **Odporność:** awaria każdej zależności po kolei (giełda, CoinGecko, dostawca LLM, Valkey, R2, Grafana); oczekiwane zachowanie opisane w tabeli degradacji.
6. **Ćwiczenie DR:** zniszczenie serwera staging, odtworzenie na nowej VM (a także na VPS innego dostawcy, wariant B) z kopii, pomiar RTO i RPO.
7. **Prywatność:** mapa danych osobowych, retencja, eksport i usunięcie konta end-to-end, pseudonimizacja w Langfuse i logach.
8. **Runbooki:** wyciek klucza, awaria giełdy przy otwartych pozycjach bota, przeciążenie, błędne dane z giełdy, koszt LLM poza budżetem.

### Testy

| Co sprawdzamy        | Jak                                     | Narzędzie                 | Wynik poprawny                                        | Przy niepowodzeniu                       |
| -------------------- | --------------------------------------- | ------------------------- | ----------------------------------------------------- | ---------------------------------------- |
| Podatności aplikacji | Pełny skan i testy ręczne wg listy ASVS | OWASP ZAP, Burp Community | 0 wysokich i krytycznych                              | Poprawka, ponowny test; blokada G15      |
| Zależności i obrazy  | Skan                                    | Trivy, Dependabot         | 0 krytycznych bez uzasadnionego wyjątku               | Aktualizacja                             |
| Obciążenie           | Profil beta ×10                         | k6 + Grafana              | NF-01, NF-02 spełnione; 0 błędów 5xx > 0,1%           | Profilowanie, cache, skalowanie workerów |
| Wytrzymałość         | 24 h stałego ruchu                      | k6                        | Brak wycieków pamięci, stabilne opóźnienia            | Diagnoza i poprawka                      |
| Degradacja           | Wyłączanie zależności po kolei          | Toxiproxy, docker stop    | Zachowanie zgodne z tabelą degradacji; komunikat w UI | Poprawić obsługę                         |
| Odtworzenie          | Ćwiczenie DR                            | pgBackRest, Terraform     | RTO ≤ 4 h, RPO ≤ 24 h (beta)                          | Poprawić runbook i automatyzację         |
| Usunięcie danych     | Usunięcie konta testowego               | test E2E + zapytania SQL  | Brak danych osobowych w bazie i logach po 30 dniach   | Poprawić proces                          |

## E16. Wdrożenie produkcyjne i publiczne uruchomienie

**Status:** ⏸ odłożone (produkt): realizacja po obronie pracy (ADR-0008); karta bez zmian

Etap kończy się publicznym startem (GA) po zamkniętej i otwartej becie, gdy przez 30 dni bety dostępność wynosi ≥ 99,5%, a lista kontrolna gotowości jest w całości odhaczona.

| Pole       | Treść                                                                                                                                     |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Udostępnić platformę prawdziwym użytkownikom w kontrolowany sposób                                                                        |
| Zależności | G15 (bot w trybach 2–3 dopiero po G14c)                                                                                                   |
| Czas       | Zamknięta beta 3–4 tyg., otwarta beta 4 tyg., przygotowanie GA 1 tydz.                                                                    |
| Koszty     | Od tego etapu: utrzymanie 60–140 USD/mies. (zakładka Fundamenty, sekcja 9)                                                                |
| Rezultat   | Środowisko `production`, decyzja hostingowa (wariant A lub B), beta, strona statusu, dokumentacja użytkownika, publiczny Ledger, start GA |
| Bramka G16 | 30 dni bety: dostępność ≥ 99,5%, 0 incydentów bezpieczeństwa, błędy krytyczne zamknięte; lista gotowości 100%                             |

### Zakres prac

1. **Decyzja hostingowa (ADR):** na podstawie wyników E15 – wariant A (Oracle powiększony) lub B (VPS w UE); `terraform apply` dla `production`; osobne klucze age i sekrety.
2. **Produkcja:** osobna baza (nie współdzielona ze staging), WAL do R2 co 5 min (RPO 1 h → docelowo krócej), wdrożenia przez GitHub Environment `production` z ręcznym zatwierdzeniem, wdrożenie blue-green na poziomie kontenerów (Caddy przełącza ruch po teście dymnym).
3. **Migracja danych:** historia rynkowa i cechy kopiowane ze staging; Ledger startuje z pełną historią prognoz od E7.
4. **Zamknięta beta:** 30–50 zaproszonych osób; formularz zgłoszeń błędów w aplikacji; cotygodniowe poprawki.
5. **Otwarta beta:** rejestracja publiczna z limitem kont dziennie; monitoring kosztów LLM i obciążenia.
6. **Strona statusu** (Better Stack), kanał komunikatów o awariach.
7. **Dokumentacja użytkownika:** jak czytać oceny i prawdopodobieństwa, metodologia agentów, ograniczenia, FAQ, słownik pojęć.
8. **Teksty prawne w wersji roboczej** (regulamin, polityka prywatności, informacja o ryzyku); analiza prawna przed GA zgodnie z Twoją decyzją o odłożeniu jej na później.
9. **Lista gotowości GA:** kopie i DR przetestowane na produkcji, alerty skierowane do Ciebie, limity kosztów, rotacja sekretów, SEO stron aktywów (sitemap, metadane), analityka bez ciasteczek śledzących (np. Plausible self-hosted lub Umami).

### Testy

| Co sprawdzamy            | Jak                                                                     | Narzędzie                          | Wynik poprawny                                          | Przy niepowodzeniu                        |
| ------------------------ | ----------------------------------------------------------------------- | ---------------------------------- | ------------------------------------------------------- | ----------------------------------------- |
| Wdrożenie produkcyjne    | Pełny pipeline z zatwierdzeniem                                         | GitHub Actions                     | Test dymny zielony; przełączenie blue-green bez przerwy | Automatyczny powrót do poprzedniej wersji |
| Kopie produkcyjne        | Odtworzenie produkcji na osobnej VM                                     | pgBackRest                         | Sukces, dane spójne                                     | Blokada otwarcia bety                     |
| Testy dymne po wdrożeniu | Zestaw 20 kluczowych sprawdzeń (API, oceny świeże, narracje, logowanie) | Playwright, pytest                 | 100%                                                    | Automatyczny rollback                     |
| Monitoring syntetyczny   | Ścieżka logowania i strona aktywa co 5 min                              | Better Stack lub Playwright w cron | Zielone                                                 | Alert do Ciebie                           |
| Jakość w becie           | Zgłoszenia użytkowników, metryki błędów (Sentry)                        | przegląd tygodniowy                | Błędy krytyczne zamknięte w ≤ 48 h                      | Wstrzymanie otwierania rejestracji        |

## E17. Utrzymanie, optymalizacja kosztów i dalszy rozwój

**Status:** ⏸ odłożone (produkt): realizacja po obronie pracy (ADR-0008); karta bez zmian

E17 to tryb ciągły, nie jednorazowy etap: ustala rytm pracy po GA, w którym każda nowa funkcja przechodzi ten sam cykl ADR → implementacja → testy → bramka.

| Pole       | Treść                                                                                  |
| ---------- | -------------------------------------------------------------------------------------- |
| Cel        | Utrzymać jakość, koszty i bezpieczeństwo oraz rozwijać produkt bez erozji architektury |
| Zależności | G16                                                                                    |
| Czas       | Ciągły                                                                                 |
| Koszty     | Wg sekcji 9 Fundamentów; przegląd miesięczny                                           |
| Rezultat   | Rytm operacyjny, raport miesięczny, backlog rozwoju z priorytetami                     |
| Bramka     | Każda nowa funkcja ma własną mini-bramkę z tymi samymi zasadami testów                 |

### Rytm operacyjny

| Częstotliwość              | Czynność                                                                                                                                                        |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Codziennie (automatycznie) | Kopie, testy kontraktowe zewnętrznych API, kontrola kosztów LLM, monitoring syntetyczny                                                                         |
| Co tydzień                 | Retrening i decyzje promocji modeli, raport ablacji agentów, przegląd alertów i błędów Sentry, aktualizacje zależności (Dependabot)                             |
| Co miesiąc                 | Przegląd kosztów i limitów dostawców, test odtworzenia kopii, przegląd wersji modeli LLM i komunikatów o wycofaniu, raport Ledgera publikowany dla użytkowników |
| Co kwartał                 | Ćwiczenie DR, rotacja sekretów, przegląd ASVS dla nowych funkcji, przegląd ADR                                                                                  |

### Optymalizacja kosztów i wydajności

- Narracje tylko dla aktywów oglądanych lub ze zmianą oceny powyżej progu.
- Destylacja ekstrakcji zdarzeń do małego modelu otwartego, gdy wolumen przekroczy kilka tysięcy dziennie.
- Prompt caching dla stałych instrukcji systemowych; Batch API dla wszystkiego, co nie jest interaktywne.
- Partycjonowanie i retencja danych według faktycznego użycia; archiwum w R2.
- Skalowanie poziome workerów przed zwiększaniem maszyn.

### Backlog rozwoju (po GA, w kolejności)

1. Agenci rozszerzenia: Cross-Asset, Portfolio (z planu ogólnego); agent on-chain dla Solany ma własną kartę E18 poniżej.
2. Wehikuł czasu (odtwarzanie dowolnego dnia z zapisanych dowodów).
3. Lustro błędów poznawczych i stres-testy portfela.
4. Generator strategii z języka naturalnego do DSL.
5. Kolejne giełdy dla bota (Kraken, Coinbase), kontrakty perpetual z twardymi limitami dźwigni.
6. Publiczne API prognoz.
7. Badania: modele bazowe szeregów czasowych, arena agentów społeczności, cyfrowy bliźniak rynku.

Każda pozycja backlogu przed rozpoczęciem dostaje w tym dokumencie własną kartę etapu w tym samym formacie co E0–E16.

## E18. Skaner tokenów on-chain (Solana)

**Status:** ⏸ odłożone (produkt): realizacja po obronie pracy (ADR-0008); karta bez zmian

Etap kończy się, gdy dla każdego nowego tokena z pump.fun platforma w ciągu ok. 10 sekund pokazuje, kto naprawdę go trzyma, jakie portfele są powiązane i jak bardzo spadłaby cena, gdyby sprzedali. Ocena ryzyka jest rozliczana w Forecast Ledger jak każda inna prognoza. Moduł jest **wyłącznie informacyjny**: nie ma przycisku "kup" ani automatycznego snajpowania, bo na pump.fun ok. 96% traderów traci lub zarabia mniej niż 500 USD miesięcznie ([OurCryptoTalk](https://ourcryptotalk.com/news/pump-fun-96-percent-traders-losing-money)).

| Pole       | Treść                                                                                                                                                                                                                                                                                                                   |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cel        | Chronić użytkowników przed tokenami kontrolowanymi przez ukrytych operatorów; nowe źródło dowodów dla fuzji                                                                                                                                                                                                             |
| Zależności | G16 (po starcie publicznym), G13 (Telegram), G11a (kalibracja wag oceny)                                                                                                                                                                                                                                                |
| Czas       | 5–6 tygodni                                                                                                                                                                                                                                                                                                             |
| Koszty     | Helius Free: 1 mln kredytów miesięcznie, 10 zapytań RPC na sekundę ([Helius](https://helius.dev/docs/billing/plans)); przy większym ruchu plan Developer za 49 USD/mies. Strumień nowych tokenów: PumpPortal, którego Data API jest darmowe w ramach limitów ([PumpPortal](https://uithub.com/thetateman/Pump-Fun-API)) |
| Rezultat   | Moduł `onchain`: strumień premier, czytnik posiadaczy, wykrywanie operatorów, ocena 0–100, model wpływu sprzedaży, historia twórcy, agent `OnChainRisk`, strona tokenu, komendy Telegrama                                                                                                                               |
| Bramka G18 | Odczyt zgodny z eksploratorem na 50 tokenach; ocena skalibrowana na historii; zużycie kredytów < 80% limitu                                                                                                                                                                                                             |

### Zakres prac

1. **Strumień premier:** websocket PumpPortal (nieoficjalne API strony trzeciej, więc za adapterem) + zapasowo własny odczyt programu pump.fun przez RPC. Bufor ostatnich 1000 premier.
2. **Czytnik on-chain:** top 20 posiadaczy (bez krzywej, pul, lockerów i adresów spalania), pierwszych 20 kupujących, historia portfeli (liczba wcześniej handlowanych tokenów), transfery, stan krzywej i puli. Implementacja własna: kod QuantumOrb ma licencję zabraniającą użycia w innym produkcie.
3. **Wykrywanie operatorów:** graf portfeli z krawędziami "zakup w tej samej transakcji", "wspólne źródło SOL" i "transfer między posiadaczami"; operator = spójna składowa grafu.
4. **Ocena ryzyka 0–100:** pięć składowych (największy operator, świeże portfele, podaż otrzymana transferem, niesprzedani snajperzy, koncentracja top 20) i twarde flagi. Start z jawnymi wagami, potem kalibracja wag na historycznych etykietach ("spadek > 80% w 24 h") w pętli samouczenia L2.
5. **Model wpływu sprzedaży:** spadek ceny = 1 − (R / (R + q))² dla puli o stałym iloczynie, gdzie R to rezerwa tokena w puli, a q to tokeny sprzedane przez powiązane portfele.
6. **Historia twórcy:** liczba premier i odsetek, który ukończył krzywą; seryjny twórca dostaje ostrzeżenie.
7. **Integracje:** agent `OnChainRisk` publikuje `Evidence`; strona tokenu w UI; Telegram: `/token`, `/watch`, `/dev`, alerty premier spełniających filtry użytkownika i przechodzących ocenę twórcy.
8. **Budżet zapytań:** limit odczytów na skan, kolejka, cache wyników; dzienny limit skanów na konto.

### Testy

| Co sprawdzamy         | Jak                                                    | Narzędzie           | Wynik poprawny                                                                | Przy niepowodzeniu                                 |
| --------------------- | ------------------------------------------------------ | ------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------- |
| Dekodowanie kont      | Wektory testowe krzywej i puli z prawdziwych adresów   | pytest              | Wartości zgodne z eksploratorem                                               | Poprawić dekoder                                   |
| Poprawność odczytu    | 50 tokenów porównanych z Solscan (posiadacze, udziały) | skrypt              | 100% zgodności po wyłączeniu adresów infrastruktury                           | Blokada G18                                        |
| Wykrywanie operatorów | Syntetyczne grafy ze znanymi grupami                   | pytest + Hypothesis | Wszystkie grupy wykryte, 0 fałszywych połączeń                                | Poprawić reguły krawędzi                           |
| Wzór wpływu           | Porównanie z symulacją puli x·y = k                    | pytest              | Różnica < 1e-9                                                                | Poprawić implementację                             |
| Jakość oceny          | 500 historycznych tokenów z etykietami                 | MLflow, raport      | Ocena lepiej rozdziela przypadki niż sama reguła twórcy; kalibracja ECE ≤ 0,1 | Wagi pozostają jawne, bez kalibracji               |
| Odporność             | Przerwa strumienia, limit 429 z RPC                    | Toxiproxy           | Wznowienie; skan oznaczony jako niepełny, nigdy jako czysty                   | Poprawić obsługę                                   |
| Budżet                | 24 h ruchu testowego                                   | metryki             | Zużycie kredytów < 80% limitu                                                 | Ograniczyć głębokość odczytu lub plan płatny (ADR) |
