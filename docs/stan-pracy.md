# Stan pracy (aktualizowany po każdym kroku)

Ten plik pozwala wznowić pracę w nowej rozmowie z asystentem AI bez utraty kontekstu:
na początku rozmowy wystarczy poprosić o przeczytanie `CLAUDE.md` i tego pliku.

**Ostatnia aktualizacja:** 2026-11-27

## Aktualna ścieżka: praca inżynierska (od 26.11.2026, ADR-0008)

- **Ścieżka:** praca inżynierska (minimum spełniające zakres pracy), potem po obronie
  ścieżka produktu. Zakres pracy, tabela „wymóg → etap → dowód” i tabela etapów:
  `docs/dokumentacja/fundamenty.md`, sekcja 0. Mapa rozdziałów pracy: `docs/praca/README.md`.
- **Kolejność etapów** (tabela „Kolejność prac” na początku `roadmapa.md`):
  E4 → E5 → E6 → E12a → E7 → E8 → E9 → E11 → E12b. E6 może biec równolegle z E4–E5,
  E12a równolegle od razu (zalecane po E5).
- **Bramki pracy:** G4p, G5p, G6p, G7p, G8p, G9p, G11p, G12p (`testy.md`, sekcja 3a).
  Pełne bramki G4–G18 bez zmian, na ścieżkę produktu.
- **Odłożone (⏸ produkt):** E10, E10a, E11a, E13, E14 (a–c), E15, E16, E17, E18; z E0 Resend;
  w etapach ścieżki pracy podsekcje „Dokończenie w ścieżce produktu”.
- **Sposób pracy:** `CLAUDE.md`, sekcja „Tryb ścieżki pracy” (sesja w chmurze, 1–3 PR-y
  na etap, właściciel scala Squash and merge). Start etapu: `docs/start-nowej-rozmowy.md`.
- **Następny krok:** E6 w ścieżce pracy (backend API tylko do odczytu, bez kont
  użytkowników, bramka G6p; wymaga G2 i G3, zaliczonych), nowa rozmowa w chmurze (prompt:
  `docs/start-nowej-rozmowy.md`, sekcja „Ścieżka pracy”); pierwszy PR E6: `gates/G6p.yaml`
  i job `gate-next` dla G6p. E7 (wymaga G5p, zaliczonej 27.11.2026) uruchamia też worker
  cech na staging (decyzja właściciela 27.11.2026). Podpis: właściciel podpisuje każdy PR
  asystenta przed scaleniem (`CLAUDE.md`, tryb pkt 3).

## Gdzie jesteśmy

- **E5 (ścieżka pracy):** zakres pracy zakończony, G5p zaliczona 27.11.2026
  (`docs/gates/G5p.passed.json`, dowód ci: przebieg 46053939823; raport `docs/gates/G5p.md`).
  PR-y: #133 (`MarketView(as_of, known_at)`, 19 cech `fs-1p` w Polars, testy G5p), #134
  (migracja 0004, zapis cech w Postgresie, zadanie po `candle.closed`, `features.ready` v2,
  konsument strumienia, przekaźnik z filtrem typów), PR zamykający (G5p w `ci-ok`, raport,
  wzory w `metody.md`). Decyzje właściciela 27.11.2026 (karta E5): klucz cech
  `(asset_id, quote_asset_id)` + `status`, `known_at` tylko w replay, worker na staging
  w E7, korelacja BTC z BTC = `not_applicable`. Worker nie działa jeszcze na staging
  (tabela `feature_values` na staging pusta do E7).
  Audyt E5 (28.11.2026, PR z gałęzi `claude/E5-audyt-poprawki`): próg wartości
  referencyjnych bezwzględny < 1e-9 (wcześniej względny), połowa chwil testu point-in-time
  na pełnej godzinie, test MACD vs `talib.MACD`, opis ograniczenia `ingested_at` z E4,
  ADR-0003 (correlation_id, filtr typów), lekcje.

- **E4 (ścieżka pracy):** zakres pracy zakończony, G4p zaliczona 27.11.2026
  (`docs/gates/G4p.passed.json`, dowód mixed: CI 45973429769 + `data-report.yml`
  45981882350; raport `docs/gates/G4p.md`). PR-y: #129 (moduł `marketdata`, G4p), #130
  (sonda z Amsterdamu: OKX i Bybit 20/20 par od 2023-01-01), #131 (proces `ingest` na
  staging, raport danych, kasety Bybit), PR zamykający (G4p w `ci-ok`, raport, dokumentacja).
  Na staging działa usługa `ingest` (co godzinę, 2 min po pełnej): 20 par × OKX i Bybit,
  1,37 mln świec od 2023-01-01, kompletność 100%, 0 luk. Wstrzymanie bez zatrzymania usługi:
  `GOATCASH_INGEST_PAUSED=1`. Podział PR 2 na 2a i 2b (4 PR-y zamiast 3): zgoda właściciela
  27.11.2026. Odkryte i poprawione: ruleset wymaga podpisu każdego commitu w PR (`CLAUDE.md`,
  tryb pkt 3; lekcja E4).

- **E0:** zakończony, G0 zaliczona (`docs/gates/G0.passed.json`, dowód lokalny). R2 i bot
  Telegram zamknięte dowodem z E3 (roadmapa E0, punkty 4 i 7; decyzja właściciela
  26.11.2026); Resend (klucz API i sprawdzenie) przechodzi do produktu (E13). PR 0
  (`doctor.sh`: R2 i Telegram) nie jest już potrzebny; gałąź `claude/E0-doctor-r2-telegram`
  do usunięcia przez właściciela.
- **E1:** zakończony i domknięty, G1 zaliczona (`docs/gates/G1.passed.json`, przebieg 45027155138).
  - PR #1 (E1), #12 (dokumentacja w repo, dowody bramek), #13 (`gate-guard`) scalone.
  - Wymagane checki `main`: `ci-ok` i `gate-guard`.
- **E2:** zakończony, G2 zaliczona (`docs/gates/G2.passed.json`, przebieg 45144539739;
  raport `docs/gates/G2.md`). Zasady współpracy z asystentem w `CLAUDE.md` (PR #16).
  - Wymagane checki `main`: `ci-ok` (od teraz z bramkami G1 i G2) i `gate-guard`
    (przez `pull_request_target`, z `main`).
- **E3:** zakończony, G3 zaliczona 25.11.2026 (`docs/gates/G3.passed.json`, dowód mixed;
  raport `docs/gates/G3.md` z dowodami, próbami nieudanymi i odstępstwami). Staging działa:
  `https://api.goatcash.app/v1/health`. Wymagane checki `main`: `ci-ok` (od teraz z G1–G3)
  i `gate-guard`.
  - PR-y po dużym PR: #92 (certyfikat i sekrety SOPS), #94 (Ansible na Ubuntu 24.04),
    #96 (alerty i Lynis), #98 (`backup-now`), #100 (`restore-test`), #102 i #105
    (odtworzenie od zera, czekanie na koniec recovery), PR zamykający E3.
  - Infrastruktura (adresy po odtworzeniu od zera 25.11.2026): A1 `143.47.189.234`,
    executor (zarezerwowane IP) `158.101.201.247`; obie maszyny w Tailscale.
- **Rozliczenie E3 (25–26.11.2026, przed E4):** właściciel: „musimy zrobić wszystko co nie
  zostało zrobione. wszystko ma być jak w dokumentacji”. Zrobione: #110 (Trivy arm64,
  obrazy bazowe po digeście), #113 (`make ansible-test` w G3, poprawka pliku wymiany),
  #114 (pełna aktualizacja, poprawki co godzinę, restart 03:30), #115 (logi kontenerów
  do Loki: 5643 linie w 30 min po wdrożeniu). Na serwerach: `ansible-staging` 45732122197
  (aktualizacja i restart obu), `external-scan` 45733147740 (0 portów, Lynis 0 ostrzeżeń
  na obu), #117 (przypięte odciski kluczy apt Docker i Tailscale, ADR-0007). #119 (metryka
  najstarszej kopii i alert „Retencja kopii nie dziala”, > 39 dni; reguła w Grafanie
  `inactive ok`), #121 (ślady OTel z api do Tempo). Ten PR: dokumentacja rozliczenia (G3.md, ADR-0007, testy.md,
  roadmapa, runbook wymiany serwera, lekcje), kopia ACL Tailscale. Decyzje właściciela
  26.11.2026: ACL w konsoli z kopią w repo, IAM executora w E14b, dwie ścieżki (ADR-0008).
  **Po E3, przed E4:** PR 0 z E0 (`doctor.sh`: R2 i Telegram, Tailscale na liście kont,
  ponowny dowód G0). **Do sprawdzenia:** plan Grafana Cloud po okresie próbnym (ok. 6.12),
  usunięcie kopii przez retencję (od ok. 25.12), minuty Actions (odnowienie 1.12).
- **Następny: E4 w ścieżce pracy** (pozyskiwanie danych rynkowych; wymaga G3, sprawdzone
  26.11.2026: `gate_guard.py --labels E4 --ref origin/main` → „E4 wymaga G3: zaliczona
  (dowód sprawdzony)”). Nowa rozmowa w chmurze z `docs/start-nowej-rozmowy.md`; pierwszy PR
  E4: `gates/G4p.yaml` i job `gate-next` dla G4p.
  - Sieć OCI utworzona przez właściciela (Terraform, 28 zasobów: VCN, podsieci,
    Security Lists, NSG 443 tylko z Cloudflare); polityka limitów `goatcash-always-free`.
  - Konta i tokeny zewnętrzne zweryfikowane (HTTP 200): R2, Cloudflare, Tailscale (ACL
    z testami, federacja OIDC dla CI), Grafana Cloud, Better Stack, bot Telegram.
  - **Duży PR E3 (24.11.2026, jawne odstępstwo od „jedna rzecz na PR”):** właściciel:
    „zróbmy PR naraz, trzeba przyspieszyć, testować będziemy na końcu”. PR 7–18 z planu
    w jednej gałęzi `claude/E3-infra-staging` (Terraform maszyn, Vault, Cloudflare,
    obserwowalność; Ansible; Compose; pgBackRest; workflow deploy/ansible/restore/scan/
    alert-drill; cosign; runbooki). Szczegóły i odstępstwa: ADR-0007, punkt 6.
    Molecule (wpis w PR 10 planu, nie w roadmapie) pominięte: role sprawdza ansible-lint
    (profil production), prawdziwy przebieg `ansible-staging.yml` i Lynis w `external-scan`.
- **Do uwzględnienia w planie E3** (wynik przeglądu E2):
  - obraz platformy bez `alembic.ini` (migracje nie ruszały z obrazu): naprawa w PR 4,
    test `make image-migration-test` (sprawdzenie `image-migrations` w G3);
  - model `Evidence` w FastAPI nie jest generowany z JSON Schema; zgodność pilnują tylko
    testy na przykładach kontraktu (do rozważenia generowanie albo test strukturalny).

## Plan E3 (zaakceptowany 23.11.2026; PR-y z etykietą `E3`, jedna rzecz na PR)

Decyzje właściciela (23.11.2026, propozycje asystenta zaakceptowane bez zmian):

- **D1 tryb lokalny:** asystent pracuje w Claude Code na Macu właściciela, w `git worktree`,
  na gałęziach `claude/E3-…`, z blokadami tylko w tym projekcie (`.claude/settings.local.json`,
  poza git; `docs/start-nowej-rozmowy.md`, „Blokady sesji lokalnej”); właściciel commituje
  podpisane, otwiera PR i scala. Komendy z kluczami chmury uruchamia właściciel.
- **D2 dysk:** boot A1 50 GB + boot mikro-VM 50 GB + wolumen danych 100 GB = 200 GB
  (limit Always Free); jawne odstępstwo od 150 GB z roadmapy, zapis w ADR-0007.
  Limity Always Free potwierdzone 23.11.2026 (ADR-0007): A1 1500 OCPU-h i 9000 GB-h/mies.,
  czyli jedna maszyna 2/12 naraz (odtwarzanie: najpierw zniszcz, potem twórz).
- **D3 stan Terraform:** OCI Object Storage (Always Free), wersjonowanie i blokada stanu
  (do weryfikacji w dokumentacji przed PR 6).
- **D4 dowód G3 mieszany:** przebieg CI na `main` + przebiegi GitHub Actions z ID
  sprawdzane przez `gate-guard` (deploy, test odtworzenia, nmap, Lynis) + lokalny raport
  odtworzenia od zera z czasem; zmiana `gate_guard` z niezależnym recenzentem.
- **D5 SSH tylko przez Tailscale** (22 zamknięty w Security List i `ufw`).
- **D6 Lynis:** „0 Warnings” (doprecyzowanie z `accepted`).
- **D7 Sentry:** przepięcie na konto projektu w E6.
- **D8 Compose:** kontener `api` (obraz `platform`) dla `/health` i testu dymnego;
  rekord `app.` bez backendu do E12.

| #   | Gałąź                              | Zakres                                                                                     | Stan        |
| --- | ---------------------------------- | ------------------------------------------------------------------------------------------ | ----------- |
| 0a  | `docs/E3-tryb-lokalny`             | tryb lokalny i zasada zgody na koszty w `CLAUDE.md`, blokady sesji, lekcja `push --delete` | ⏳          |
| 0   | `feat/E0-doctor-r2-telegram`       | `doctor.sh`: R2 i Telegram; zbędny: ⚠️ E0 zamknięte dowodem z E3 (26.11.2026)              | zbędny      |
| 1   | `docs/E3-adr-infra`                | ADR-0007: D2–D6, model dowodu, budżet Always Free                                          | ✅ (PR #76) |
| 2   | `ci/E3-bramka-g3`                  | `gates/G3.yaml` (czerwona), szkic `G3.md`, job G3 poza `ci-ok`                             | ✅ (PR #78) |
| 3   | `ci/E3-dowod-mieszany`             | `gate_pass.py`/`gate_guard.py`: dowód mieszany + testy obejścia, niezależna recenzja       | ✅ (PR #80) |
| 4   | `fix/E3-obraz-alembic`             | `alembic.ini` i migracje w obrazie; test `upgrade head` z obrazu                           | ✅ (PR #82) |
| 5   | `ci/E3-narzedzia-iac`              | Terraform, tflint, ansible-lint, trivy config w `make tools`/`audit`                       | ✅ (PR #84) |
| 6   | `feat/E3-tf-oci-siec`              | VCN, podsieci, Security Lists (443 tylko z Cloudflare, bez 22)                             | ✅ (PR #86) |
| 7   | `feat/E3-tf-oci-maszyny`           | A1 2/12, wolumen, mikro-VM, zarezerwowane IP                                               | ✅ (PR #90) |
| 8   | `feat/E3-tf-oci-vault`             | Vault, klucz główny; polityka instancji executora przeniesiona do E14b (ADR-0007, 26.11)   | ✅ (PR #90) |
| 9   | `feat/E3-tf-cloudflare`            | `api.`/`app.`, proxy, SSL Full strict, WAF, limit zapytań, R2, Origin CA, tokeny           | ✅ (PR #90) |
| 10  | `feat/E3-ansible-hardening`        | użytkownik, SSH kluczem, fail2ban, aktualizacje, ufw, swap, journald; Molecule             | ✅ (PR #90) |
| 11  | `feat/E3-ansible-docker-tailscale` | Docker, Tailscale; ACL w konsoli, kopia `infra/tailscale/acl.hujson` (ADR-0007, 26.11)     | ✅ (PR #90) |
| 12  | `feat/E3-compose-staging`          | Postgres 17 + Timescale + pgvector, Valkey AOF, Caddy, otel, exportery, `api`              | ✅ (PR #90) |
| 13  | `feat/E3-pgbackrest`               | pełna/przyrostowa/WAL, szyfrowanie, retencja 30 dni; test w CI (`posix`, nie MinIO; PITR)  | ✅ (PR #90) |
| 14  | `ci/E3-test-odtworzenia`           | cotygodniowe odtworzenie z R2 do czystej instancji, 100% tabel (F-02)                      | ✅ (PR #90) |
| 15  | `feat/E3-obserwowalnosc`           | OTel → Grafana Cloud, pulpity, 3 alerty, e-mail i Telegram, Better Stack                   | ✅ (PR #90) |
| 16  | `ci/E3-deploy-staging`             | `deploy-staging.yml`: Tailscale, cosign, pull/up, migracje, test dymny, rollback           | ✅ (PR #90) |
| 17  | `docs/E3-runbooki`                 | odtworzenie z kopii, rotacja sekretów, wymiana serwera                                     | ✅ (PR #90) |
| 18  | `docs/E3-g3`                       | bramka, raport, dowód, „Stan realizacji E3”, README, lekcje                                | ✅ ten PR   |

## Plan E2 (zrealizowany; PR-y z etykietą `E2`, jedna rzecz na PR)

| #   | Gałąź                      | Zakres                                                                                       | Stan             |
| --- | -------------------------- | -------------------------------------------------------------------------------------------- | ---------------- |
| 0   | `docs/E2-spojnosc-g1`      | nagłówek `G1.md` (zaliczona), tytuł roadmapy E0–E18, ten plan (PR #18)                       | ✅               |
| 0a  | `ci/E2-gate-guard-wyscig`  | `gate-guard`: etykiety z API, bez `opened` i bez anulowania przebiegów (PR #20)              | ✅               |
| 1   | `ci/E2-bramka-g2`          | `gates/G2.yaml` + szkic `docs/gates/G2.md`; bramka czerwona, dopóki nie ma treści            | ✅ (PR #22)      |
| 2   | `docs/E2-adr`              | ADR-002 model danych, 003 Valkey Streams, 004 uwierzytelnianie, 005 bramka LLM, 006 executor | ✅ (PR #24)      |
| 2a  | `docs/E2-auth-drift-e6`    | porównanie schematu Better Auth przeniesione z G2 do E6/G6 (zgodnie z roadmapą)              | ✅ (PR #27)      |
| 3   | `feat/E2-migracja-0001`    | Alembic, migracja 0001, test `upgrade head` / `downgrade base` (testcontainers)              | ✅ (PR #30)      |
| 4   | `feat/E2-schematy-zdarzen` | JSON Schema 8 zdarzeń z `schema_version`, testy poprawnych i błędnych przykładów             | ✅ (PR #32)      |
| 5   | `feat/E2-evidence-v1`      | kontrakt `Evidence` v1 + testy                                                               | ✅ (PR #34)      |
| 6   | `feat/E2-openapi`          | szkic OpenAPI 3.1 z FastAPI `/v1`, Spectral w CI, klient TS w `packages/contracts`           | ✅ (PR #36)      |
| 7   | `docs/E2-wymagania`        | F-xx i NF-xx w `docs/wymagania.yaml` + skrypt kompletności                                   | ✅ (PR #40)      |
| 8   | `docs/E2-stride`           | model zagrożeń STRIDE: API, executor, panel administratora                                   | ✅ (PR #43)      |
| 9   | `docs/E2-c4`               | diagram C4 (kontekst, kontenery) w Mermaid                                                   | ✅ (PR #44)      |
| 10a | `ci/E2-gate-guard-target`  | luka: PR mógł podmienić `gate-guard.yml`; `pull_request_target` (dowód: szkice #50, #51)     | ✅ (PR #46, #48) |
| 10  | `docs/E2-g2`               | bramka na `main`, raport `G2.md`, `G2.passed.json`                                           | ✅ (PR #54)      |

Domknięcie E2 (po G2): PR #58 (prompt nowej rozmowy, ograniczenia sesji), #59 (ponowienia
`curl` w `make tools`, zamyka #25), #64 (progi wymagań zaakceptowane, F-36), #66 (README
po E2 i test aktualności), #68 (NF-06 zgodne z roadmapą), PR z tabelą „Stan realizacji E2”
w roadmapie i `docs/lekcje.md`.

Decyzje właściciela do planu (22.11.2026):

- Wymagania w `docs/wymagania.yaml` (sprawdzane skryptem), C4 w Mermaid.
- Test migracji (testcontainers) tylko na ubuntu: runnery macOS w GitHub Actions nie mają
  Dockera. Na macOS bramka G2 sprawdza schematy, Spectral i wymagania. Jawne odstępstwo,
  zapisane w `docs/gates/G2.md`.
- Tabele Better Auth tworzy nasza migracja Alembic (jedno źródło schematu). Wykrywanie
  rozjazdu po aktualizacji Better Auth opisuje ADR-0004; sprawdzenie powstaje w E6 razem
  z konfiguracją Better Auth i należy do G6 (właściciel zostawił wybór asystentowi: zgodnie
  z roadmapą, bez dokładania pracy do E2).

## Otwarte sprawy

- **Przed workerem cech na staging (E7), decyzja właściciela:** upsert ceny referencyjnej
  w E4 nadpisuje `ingested_at` (`marketdata/_impl/pgstore.py`), więc replay z `known_at`
  widzi poprawioną świecę jako lukę przed jej aktualizacją (bez przecieku, ale niewiernie).
  Opcje: kolumna `first_ingested_at` w `candles_ref` (rekomendacja) albo wersje świec
  (audyt E5 28.11.2026, `docs/gates/G5p.md`).
- E3 (zakończony): infrastruktura utworzona przez właściciela (plan → zgoda → uruchomienie):
  `oci-trwale`, `oci`, `cloudflare`, `observability`; tokeny R2 (zapis: pgBackRest, odczyt:
  test kopii), `staging.enc.yaml`, sekrety środowisk `staging` i `staging-readonly`, dwa
  klienty OIDC Tailscale (subject w formacie niezmiennym repozytorium), klient OAuth
  `goatcash-terraform` z tagiem-właścicielem. Szczegóły: ADR-0007 pkt 6, `docs/gates/G3.md`.
- E3: środowisko `staging` **bez wymaganego recenzenta, tylko gałąź `main`** (decyzja
  właściciela 24.11.2026): recenzent blokował automatyczne wdrożenie z `main`
  i odtworzenie „bez ręcznych kroków” (G3); roadmapa wymaga zatwierdzania tylko dla
  `production`. Ochrona: ruleset `main` (tylko właściciel scala), środowiska tylko z `main`.
- E3: Grafana Cloud w okresie próbnym do ok. 6.12.2026: sprawdzić, że stos przechodzi
  na plan Free (bez karty), i że limity Free wystarczają (metryki, logi).
- E0: R2 i bot Telegram ✅ z dowodem z E3 (R2: kopie pgBackRest i `restore-test`
  45502801764; Telegram: `alert-drill` 45494553367). Resend: tylko konto; domena
  `goatcash.app` w Resend, klucz API i sprawdzenie w E13 (⏸ produkt).
- Sentry na koncie prywatnym: przepięcie na konto projektu ⏸ produkt (w ścieżce pracy
  Sentry nie jest używany).
- Graphify wyłączony do końca pracy (decyzja właściciela 26.11.2026; wyłącza właściciel
  w ustawieniach GitHub App). **Do sprawdzenia:** na PR #130 (27.11.2026) pojawił się check
  „Graphify Formal Verification” (neutralny), więc aplikacja nadal działa na repozytorium.
- E4: środowisko sesji asystenta „crypto_inteligence_app” (własne, z dostępem do
  `www.okx.com` i `api.bybit.com` do nagrań kaset; Bybit blokuje kraj sesji, kasety Bybit
  nagrywa `marketdata-probe.yml` na serwerze). Repozytorium jest publiczne (`gh repo view`, 26.11.2026).
- Błędy asystenta z E0–E2 i jak ich unikamy: `docs/lekcje.md`.
- Stary ruleset „Protect main” usunięty przez właściciela (API 23.11.2026: aktywny tylko
  `main-protection`).
- Potwierdzone przez właściciela 23.11.2026: ustawienia Actions („Require approval for all
  external contributors”, „Require actions to be pinned to a full-length commit SHA”)
  i poprawne renderowanie `docs/architektura/c4.md` na GitHubie.
- Zgłoszenia `tech-debt` otwarte: #60 (uszkodzony plik dowodu → wyjątek w `gate_guard`),
  #61 (paginacja jobów > 100), #62 (stary `coverage.xml` w progu pokrycia).
- Nowy klucz Anthropic przed 19.02.2027.
- Graphify: uwagi z PR #12 i #13 przejrzane przez konektor 23.11.2026 (Graphify udostępnia
  5 najważniejszych z 18; triaż w rozmowie o domknięciu E2, drobiazgi jako zgłoszenia
  `tech-debt`). Limit przeglądów Graphify (10/miesiąc) wyczerpany na E1: PR-y E2 nie miały
  przeglądu Graphify; odnowienie 1.12.2026.
- Atrybucja „Data by CoinGecko” w interfejsie: w E12.
- Logo w README (PR #28, poza planem E2, zgłoszone przez właściciela).
- Migracja 0001 (PR 3): `make db-migration-test` wymaga Dockera (u właściciela Docker Desktop,
  w CI job G2 na ubuntu); w `make test` test migracji jest wyłączony markerem `migration`.
- Progi `source: doprecyzowanie` w `docs/wymagania.yaml` zaakceptowane lub zmienione przez
  właściciela 23.11.2026 (pole `accepted` i `note`, wymagane przez `make requirements-check`);
  F-23 rozdzielone na F-23 (pułapka z przyszłą ceną) i F-36 (przeuczenie: DSR/PBO).
- NF-06: `source: roadmapa` (WCAG 2.2 AA oznacza w axe 0 critical i 0 serious); wiersz
  „Dostępność UI” w `testy.md` ujednolicony.
- Zgłoszenie #25 (`tech-debt`, ponowienia `curl` w `install-tools.sh`) zamknięte przez PR #59.
- Ryzyko przyjęte (G2.md): PR może zmienić `ci.yml`; ochrona przez przegląd `.github/`,
  zatwierdzanie workflow z forków (zalecane: „Require approval for all external
  contributors”) i `gate-guard` z `main`.

## Jak pracujemy (skrót; pełne zasady: `CLAUDE.md` i `CONTRIBUTING.md`)

- **Teraz (ścieżka pracy):** asystent w sesji w chmurze sam pisze kod i testy, wypycha
  gałąź `claude/E<nr>-…`, otwiera właściwy PR z etykietą etapu i poprawia go do zielonego
  CI; właściciel przegląda i scala Squash and merge w GitHubie. 1–3 PR-y na etap,
  dokumentacja przy domknięciu etapu, bez niezależnego recenzenta (poza zmianami kontroli
  bramek i sekretów) i bez Graphify.
- **Po powrocie do produktu:** szkic `claude/…` do testu CI, właściciel przenosi zmianę na
  swoją gałąź (podpis SSH), jedna rzecz na PR, triaż uwag Graphify i Copilota
  (`CLAUDE.md`, „Zasady współpracy”).
- PR-y Dependabota mają etykietę `dependencies` (gate-guard je przepuszcza); duże wersje
  są wyłączone regułami w `.github/dependabot.yml`.
