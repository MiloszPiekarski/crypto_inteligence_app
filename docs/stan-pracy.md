# Stan pracy (aktualizowany po każdym kroku)

Ten plik pozwala wznowić pracę w nowej rozmowie z asystentem AI bez utraty kontekstu:
na początku rozmowy wystarczy poprosić o przeczytanie `CLAUDE.md` i tego pliku.

**Ostatnia aktualizacja:** 2026-11-26

## Gdzie jesteśmy

- **E0:** zakończony, G0 zaliczona (`docs/gates/G0.passed.json`, dowód lokalny).
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
  na obu), #117 (przypięte odciski kluczy apt Docker i Tailscale, ADR-0007). W toku:
  metryka najstarszej kopii i alert „Retencja kopii nie dziala” (> 39 dni). Dalej: ślad w Tempo, ACL Tailscale jako kod i IAM executora, E0 (doctor.sh,
  ponowny dowód G0), poprawki dokumentacji (G3.md, testy.md, roadmapa, lekcje).
- **Następny: E4** (pozyskiwanie danych rynkowych i normalizacja; wymaga G3). Nowa rozmowa
  z `docs/start-nowej-rozmowy.md`; pierwszy PR E4: `gates/G4.yaml` i job `gate-next` dla G4.
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
| 0   | `feat/E0-doctor-r2-telegram`       | `doctor.sh`: R2 (lista bucketów) i Telegram (`getMe` + wiadomość); zamyka ⚠️ E0            | ⬜          |
| 1   | `docs/E3-adr-infra`                | ADR-0007: D2–D6, model dowodu, budżet Always Free                                          | ✅ (PR #76) |
| 2   | `ci/E3-bramka-g3`                  | `gates/G3.yaml` (czerwona), szkic `G3.md`, job G3 poza `ci-ok`                             | ✅ (PR #78) |
| 3   | `ci/E3-dowod-mieszany`             | `gate_pass.py`/`gate_guard.py`: dowód mieszany + testy obejścia, niezależna recenzja       | ✅ (PR #80) |
| 4   | `fix/E3-obraz-alembic`             | `alembic.ini` i migracje w obrazie; test `upgrade head` z obrazu                           | ✅ (PR #82) |
| 5   | `ci/E3-narzedzia-iac`              | Terraform, tflint, ansible-lint, trivy config w `make tools`/`audit`                       | ✅ (PR #84) |
| 6   | `feat/E3-tf-oci-siec`              | VCN, podsieci, Security Lists (443 tylko z Cloudflare, bez 22)                             | ✅ (PR #86) |
| 7   | `feat/E3-tf-oci-maszyny`           | A1 2/12, wolumen, mikro-VM, zarezerwowane IP                                               | ✅ (PR #90) |
| 8   | `feat/E3-tf-oci-vault`             | Vault, klucz główny, polityka instancji executora                                          | ✅ (PR #90) |
| 9   | `feat/E3-tf-cloudflare`            | `api.`/`app.`, proxy, SSL Full strict, WAF, limit zapytań, R2, Origin CA, tokeny           | ✅ (PR #90) |
| 10  | `feat/E3-ansible-hardening`        | użytkownik, SSH kluczem, fail2ban, aktualizacje, ufw, swap, journald; Molecule             | ✅ (PR #90) |
| 11  | `feat/E3-ansible-docker-tailscale` | Docker, Tailscale, ACL                                                                     | ✅ (PR #90) |
| 12  | `feat/E3-compose-staging`          | Postgres 17 + Timescale + pgvector, Valkey AOF, Caddy, otel, exportery, `api`              | ✅ (PR #90) |
| 13  | `feat/E3-pgbackrest`               | pełna/przyrostowa/WAL, szyfrowanie, retencja 30 dni; test w CI (MinIO, PITR, sumy)         | ✅ (PR #90) |
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
- ⚠️ E0: R2, Resend i bot Telegram założone (według właściciela, 22.11.2026), w repo brak
  dowodu, w `.env.local` brak kluczy. Decyzja: R2 i Telegram dostają sprawdzenie w `doctor.sh`
  (osobny PR E0, klucze tylko do odczytu w `.env.local`); Resend ma na razie tylko konto,
  domena `goatcash.app` w Resend, klucz API i sprawdzenie dochodzą w E13 (do tego czasu ⚠️).
- Sentry na koncie prywatnym: przepiąć na konto projektu w E3/E6.
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

## Jak pracujemy (skrót; pełne zasady: `CLAUDE.md`, sekcja „Zasady współpracy”, i `CONTRIBUTING.md`)

- Asystent przygotowuje zmiany jako łatki (`git apply`), wcześniej testuje je na gałęzi
  `claude/…` w szkicu PR (CI na Linuksie i macOS); właściciel nakłada, commituje (podpis SSH),
  otwiera PR z etykietą etapu i scala.
- Niezależny recenzent (osobny agent) tylko wtedy, gdy zmiana tego wymaga (sekrety,
  bezpieczeństwo) i po zgodzie właściciela: jest drogi i trwa długo.
- Uwagi Graphify i Copilota: asystent robi triaż (naprawiamy / odpowiadamy / ignorujemy)
  i daje gotowe odpowiedzi; kod zmieniamy tylko przy problemach bezpieczeństwa,
  poprawności albo bramki.
- PR-y Dependabota mają etykietę `dependencies` (gate-guard je przepuszcza); duże wersje
  są wyłączone regułami w `.github/dependabot.yml`.
