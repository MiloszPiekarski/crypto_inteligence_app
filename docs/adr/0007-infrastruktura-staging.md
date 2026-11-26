# ADR-0007: Infrastruktura staging: budżet zasobów, stan Terraform, dostęp i dowód G3

- **Status:** przyjęta (decyzje D2–D6 zaakceptowane przez właściciela 23.11.2026; punkt 6
  uzupełniany do 25.11.2026; potwierdzona zaliczeniem G3, `docs/gates/G3.md`)
- **Data:** 2026-11-23
- **Etap:** E3
- **Źródło:** roadmapa E3 (zakres prac 1–7, tabela testów), `docs/stan-pracy.md` (decyzje
  D1–D8), ADR-0001, ADR-0006, `docs/architektura/stride.md`, wymagania F-01, F-02, F-03

## Kontekst

E3 tworzy pierwsze prawdziwe zasoby. Roadmapa zakłada koszt 0 (Oracle Always Free,
Cloudflare Free, Grafana Cloud Free), a konto Oracle jest **Pay As You Go**: zasób spoza
Always Free nalicza opłatę (alarm budżetu 1 USD to alarm, nie blokada). Środowisko musi
dać się odtworzyć od zera w < 30 min bez ręcznych kroków (F-01), mieć kopie odtwarzalne
z identycznymi sumami kontrolnymi (F-02) i alerty w < 5 min (F-03). Z internetu ma być
otwarty tylko 443 przez Cloudflare. Część dowodów bramki G3 powstaje na prawdziwej
infrastrukturze, a nie w CI, a obecny `gate_guard` przyjmuje albo dowód z CI, albo dowód
w pełni lokalny (G0).

## Decyzja

### 1. Budżet zasobów Oracle (D2): wszystko w Always Free

| Zasób                                | Ilość                     | Uwagi                                    |
| ------------------------------------ | ------------------------- | ---------------------------------------- |
| VM Ampere A1 (arm64)                 | 1 × 2 OCPU / 12 GB        | roadmapa E3; serwer platformy            |
| VM AMD `VM.Standard.E2.1.Micro`      | 1                         | executor (ADR-0006), zarezerwowane IP    |
| Dysk startowy A1                     | 50 GB                     | minimum dysku startowego OCI to 50 GB    |
| Dysk startowy mikro-VM               | 50 GB                     |                                          |
| Wolumen danych A1 (Postgres, Valkey) | **100 GB** (roadmapa 150) | **jawne odstępstwo**, patrz niżej        |
| Razem dyski                          | 200 GB                    | limit Always Free: 200 GB (potwierdzone) |
| Object Storage (stan Terraform)      | < 1 GB                    | bucket z wersjonowaniem                  |
| OCI Vault                            | 1 klucz główny (AES, HSM) | ADR-0006; vault typu DEFAULT, nie VPV    |

**Odstępstwo od roadmapy:** wolumen danych 100 GB zamiast 150 GB. Przy 150 GB dyski
razem miałyby ok. 250 GB i przekroczyły limit Always Free, co na koncie PAYG oznacza
opłatę. Kopie trafiają na R2 (nie na dysk), a dane rynkowe pojawią się dopiero w E4, więc
100 GB wystarcza na E3–E5; alert dysku > 80% (F-03) ostrzeże z wyprzedzeniem. Zwiększenie
wolumenu w przyszłości to zmiana jednej wartości w Terraform i jawna decyzja kosztowa.

**Limity Always Free potwierdzone przez właściciela 23.11.2026** (strona
https://www.oracle.com/cloud/free/, filtr „Always Free”; strona zwraca automatom 404/403,
więc źródłem są zrzuty ekranu właściciela):

| Usługa          | Limit Always Free (strona Oracle, 23.11.2026)                                 |
| --------------- | ----------------------------------------------------------------------------- |
| Arm (Ampere A1) | **1500 OCPU-godzin i 9000 GB-godzin miesięcznie** („1 VM or 2 VMs”, 12 GB)    |
| AMD             | 2 maszyny (1/8 OCPU, 1 GB pamięci każda)                                      |
| Block Volume    | dyski startowe i blokowe razem: do 2 wolumenów blokowych, 200 GB, 5 kopii     |
| Object Storage  | 20 GB łącznie (standard, infrequent, archive), 50 000 zapytań API miesięcznie |
| Vault           | 20 wersji kluczy HSM, 150 sekretów (vault typu DEFAULT)                       |
| Bastions        | do 5 (awaryjny dostęp SSH bez publicznego portu; na razie nieużywane)         |

**Korekta:** pierwsza wersja tego ADR podawała dla A1 3000 OCPU-godzin i 18 000 GB-godzin
(dokumentacja OCI z Context7); aktualna strona Oracle podaje połowę. Wnioski:

- maszyna A1 2 OCPU / 12 GB działająca bez przerwy w 31-dniowym miesiącu (744 h) zużywa
  1488 OCPU-godzin i 8928 GB-godzin: **mieści się, ale na styk** (zapas 12 OCPU-h, 72 GB-h);
- **w danej chwili może istnieć tylko jedna maszyna A1 2/12.** Odtworzenie od zera (F-01)
  najpierw niszczy starą maszynę, potem tworzy nową; test odtworzenia kopii (F-02) nie
  tworzy drugiej A1 obok działającej (odtwarza do kontenera na runnerze CI albo na tej
  samej maszynie). Druga A1, choćby na godzinę, może przekroczyć limit miesięczny;
- dyski: 50 + 50 + 100 = 200 GB to cały limit: żadnego dodatkowego wolumenu ani większego
  dysku startowego bez decyzji kosztowej;
- Vault: wyłącznie typ DEFAULT z kluczem HSM; „Virtual Private Vault” jest płatny
  (polityka w PR z Vault Terraform).

Dysk startowy od 50 GB: dokumentacja OCI „Creating an Instance”.

**Twarda blokada kosztów:** oprócz alarmu 1 USD właściciel ustawia w konsoli **limity
(quota policies) compartmentu `goatcash`** na poziomie Always Free (rdzenie i pamięć A1,
liczba mikro-VM, łączna pojemność dysków). Przekroczenie kończy się błędem Terraform,
a nie rachunkiem. Polityki limitów wymagają uprawnień w compartmencie głównym, więc
ustawia je właściciel (instrukcja w PR z siecią Terraform).

### 2. Stan Terraform (D3): backend `oci` w Object Storage

- Backend `oci` Terraform (dokumentacja HashiCorp „Backend type: oci”): stan w osobnym
  buckecie OCI Object Storage z **wersjonowaniem** (odzyskanie poprzedniego stanu)
  i **blokadą** (plik `.lock` tworzony przez `If-None-Match: *`).
- Bucket na stan tworzy jednorazowo właściciel (komenda OCI CLI w runbooku), bo stan nie
  może zarządzać własnym bucketem. Uwierzytelnienie: profil `~/.oci/config` właściciela
  (częściowa konfiguracja backendu, żadnych kluczy w repo).
- Stan nie leży u dostawcy, którym ten sam Terraform zarządza (Cloudflare/R2), więc awaria
  lub zła zmiana po stronie Cloudflare nie odcina stanu.
- Minimalna wersja Terraform z backendem `oci` zostanie sprawdzona i przypięta w PR
  z narzędziami IaC (`.terraform.lock.hcl` dla providerów).

### 3. Dostęp administracyjny (D5): tylko Tailscale

- Security Lists i `ufw`: **brak portu 22 z internetu**. Przychodzący 443 tylko z zakresów
  IP Cloudflare (lista pobierana przez provider Cloudflare w Terraform). Mikro-VM executora
  nie ma żadnych portów przychodzących (ADR-0006).
- Pierwsze uruchomienie: `cloud-init` instaluje Tailscale i dołącza maszynę do sieci
  jednorazowym, krótkotrwałym (1 h), wstępnie zatwierdzonym kluczem z tagiem serwera. Klucz
  trafia do metadanych instancji (czytelnych z maszyny), dlatego jest jednorazowy i po
  dołączeniu bezużyteczny. Ansible od początku łączy się przez Tailscale.
- Awaryjny dostęp bez Tailscale: konsola szeregowa OCI (właściciel, przez konsolę Oracle).
- `deploy-staging.yml` łączy się przez Tailscale (klient OAuth z tagiem CI, ACL tylko do
  serwera staging), nie przez publiczny SSH.

### 4. Kryterium Lynis (D6)

Audyt Lynis jest zaliczony przy **0 pozycji „Warnings”** w raporcie (Lynis nie ma poziomu
„krytyczne”); „Suggestions” trafiają do raportu `G3.md` z decyzją (naprawa albo
uzasadnienie). Indeks hardeningu zapisujemy dla porównania w kolejnych etapach.

### 5. Dowód bramki G3 (D4): dowód mieszany

Każde sprawdzenie G3 ma źródło, które da się zweryfikować:

| Sprawdzenie                                                                                    | Gdzie działa                                                  | Dowód                                       |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------- |
| Statyczne (fmt/validate, tflint, ansible-lint, Compose, testy skryptów, test kopii na `posix`) | CI (`ci.yml`, job bramki G3)                                  | ID przebiegu na `main` (jak G1, G2)         |
| Wdrożenie z testem dymnym i rollbackiem                                                        | `deploy-staging.yml` na `main`                                | ID przebiegu, sprawdzany przez `gate-guard` |
| Test odtworzenia kopii (F-02, tygodniowy)                                                      | workflow z harmonogramem                                      | ID przebiegu, sprawdzany przez `gate-guard` |
| Skan z zewnątrz (nmap) i Lynis                                                                 | workflow na runnerze GitHub (Tailscale do Lynis)              | ID przebiegu                                |
| Alerty < 5 min (dysk, zatrzymany kontener)                                                     | workflow ćwiczenia alertów (cel); w razie braku API: lokalnie | ID przebiegu albo raport lokalny            |
| Odtworzenie środowiska od zera < 30 min (F-01)                                                 | komputer właściciela (klucze chmury)                          | raport lokalny z czasem, bez sekretów       |

`gate_guard` dostaje nowy typ dowodu `mixed`: przebieg `ci.yml` na `main` plus lista ID
przebiegów nazwanych workflow (każdy: zielony, `main`, ten sam commit albo nowszy niż
wskazany) plus raporty lokalne z sumą SHA-256 zapisaną w pliku dowodu. Zmiana `gate_guard`
to osobny PR z testami obejścia i niezależnym recenzentem (ryzyko: `pull_request_target`).
Raport lokalny jest oświadczeniem właściciela (jak G0), dlatego ograniczamy go do jednego
sprawdzenia, którego nie da się bezpiecznie przenieść do CI (klucze Oracle i Cloudflare
zostają na komputerze właściciela).

### 6. Realizacja i jawne odstępstwa (24.11.2026, duży PR E3)

Właściciel 24.11.2026: „zróbmy PR naraz, trzeba przyspieszyć, testować będziemy na końcu”.
Pozostała część E3 (plan PR 7–18 w `docs/stan-pracy.md`) trafia w jednym PR, a nie w
osobnych (**jawne odstępstwo od „jedna rzecz na PR”**). Ustalenia z realizacji:

- **Monitorowanie `/v1/health`:** Grafana Synthetic Monitoring co 60 s (Frankfurt, alert
  po 2 min) **oraz** Better Stack co 180 s. Roadmapa: „Better Stack co minutę”; plan Free
  Better Stack pozwala najczęściej co 3 min (lista wyboru: 3, 5, 10, 15, 30 min), więc
  minutowe sprawdzenie robi Grafana (decyzja właściciela 24.11.2026). **Odstępstwo.**
- **Warstwa trwała `infra/terraform/oci-trwale`:** Vault DEFAULT z kluczem HSM
  (`prevent_destroy`) w osobnym module i stanie. Odtworzenie od zera zastępuje maszyny
  i wolumen danych, a klucza executora nie dotyka (zniszczenie vaultu = 7–30 dni oczekiwania
  i utrata kluczy).
- **Tailscale nie jest instalowany na Macu właściciela** (komputer firmowy). Ansible
  i wdrożenie działają wyłącznie z GitHub Actions: `tailscale/github-action` z federacją
  OIDC (brak stałego sekretu Tailscale w GitHub; klient z tagiem `tag:goatcash-ci`). ACL:
  `tag:goatcash-ci` → serwery tylko `tcp:22`; `tag:goatcash-executor` → serwer `tcp:5432`;
  administrator → wszystkie porty; Tailscale SSH wyłączony.
- **Sekrety staging:** `infra/secrets/staging.enc.yaml` (SOPS, klucz age `staging`).
  Klucz prywatny age jest tylko w Bitwardenie, w sekrecie środowiska GitHub `staging`
  (Ansible) i na serwerze (`/etc/goatcash/age.key`, 0400, root). Użytkownik `deploy`
  odszyfrowuje sekrety przez `sudo goatcash-render-env` (jedyne polecenie w sudoers;
  zapis bez podążania za dowiązaniami, test `scripts/tests/test_render_env.py`). **Granica
  jest słaba i to wiemy:** `deploy` jest w grupie `docker`, czyli w praktyce ma uprawnienia
  roota (może zamontować `/etc` w kontenerze). Tryb 0400 i sudoers chronią przed
  przypadkowym ujawnieniem klucza (logi, kopie katalogu), nie przed przejętym kontem
  `deploy`. Skutek przejęcia: wyciek sekretów **tylko staging** (osobny klucz age na
  środowisko). Przed produkcją do rozważenia: rootless Docker albo rozdzielenie
  użytkownika wdrożeń od grupy `docker`.
- **Środowiska GitHub (tylko gałąź `main`, bez wymaganego recenzenta; decyzja właściciela
  24.11.2026, bo recenzent blokowałby automatyczne wdrożenie i odtworzenie bez ręcznych
  kroków; ręczne zatwierdzanie dopiero dla `production`):** `staging` (wdrożenie, Ansible, ćwiczenie
  alertów: klucz SSH wdrożeń, klucz age) i `staging-readonly` (harmonogram: test kopii
  i skan). `staging-readonly` dostaje **klucz sondy** z `restrict,command=` w
  `authorized_keys` (tylko `goatcash-probe`: sumy kontrolne + punkt przywracania albo Lynis)
  i token R2 tylko do odczytu, a więc ani powłoki, ani Dockera, ani zapisu kopii.
- **Obrazy podpisane:** `ci.yml` podpisuje obrazy cosign keyless po digeście (tylko `main`);
  `deploy-staging.yml` wdraża wyłącznie obraz podpisany przez `ci.yml@refs/heads/main` tego
  repozytorium i tylko commit z zielonym `ci-ok`.
- **Odtworzenie od zera (F-01):** `scripts/g3_rebuild.sh` (właściciel, klucze chmury
  lokalnie): plan Terraform i jedno „tak” przed startem zegara, potem bez udziału człowieka:
  usunięcie starych węzłów Tailscale; usunięcie obu maszyn i wolumenu oraz **czekanie, aż
  Oracle usunie wszystkie trzy dyski** (dysk w stanie TERMINATING nadal zajmuje limit
  200 GB: dwie próby padły na LimitExceeded i bootVolumeQuota); utworzenie maszyn i wolumenu;
  zarezerwowane IP executora na czas odbudowy wyjęte ze stanu Terraform i zaimportowane
  z powrotem (zależy od maszyny przez źródła danych, a nie może się zmienić); DNS na nowe IP,
  `ansible-staging.yml`, ponowienie wdrożenia HEAD. Pusty wolumen bazy `deploy.sh` odtwarza
  z kopii w R2 (najnowsza kopia + cały WAL) i czeka na koniec odtwarzania WAL przed
  `stanza-create`; sprawdza to `make compose-staging-test`. Wynik: 1388 s, 0 ręcznych
  kroków (25.11.2026). RPO: `archive_timeout` 300 s, czyli do 5 min danych.
- **Subject OIDC Tailscale:** repozytorium ma niezmienny format subject
  (`repo:MiloszPiekarski@109043317/crypto_inteligence_app@1455875058:environment:<env>`),
  dwa klienty OIDC: dla `staging` i `staging-readonly`. Format sprawdzamy przez
  `gh api repos/<repo>/actions/oidc/customization/sub`.
- **Endpoint R2:** bucket ma wskazówkę lokalizacji EEUR, bez jurysdykcji UE, więc endpoint to
  `<account_id>.r2.cloudflarestorage.com` (bez `.eu.`).
- **Aktualizacje i Lynis:** Ansible instaluje zaległe aktualizacje i restartuje serwer, gdy
  system tego wymaga; Lynis PKGS-7388 wyłączony tylko na arm64 i tylko gdy suite
  `<wydanie>-security` jest w źródłach apt (fałszywy alarm, szczegóły w `G3.md`).
- **Test kopii (F-02, `restore-test.yml`):** sonda liczy sumy wszystkich tabel na serwerze
  i zakłada nazwany punkt przywracania; runner odtwarza kopię z R2 do tego punktu i porównuje
  sumy (100% tabel). Zgodnie z punktem 1: odtworzenie w kontenerze na runnerze, bez drugiej A1.
- **Zarezerwowane publiczne IP executora: 0 zł** (sprawdzone 24.11.2026): limit konta
  `reserved-public-ip-count` 50 (użycie 0 przed utworzeniem), cennik Oracle (sekcja
  Networking) nie ma pozycji za publiczne IP, Oracle przy wprowadzeniu funkcji: bez opłat.
  Zabezpieczenie: alarm budżetu 1 USD.
- **Polityka limitów `goatcash-always-free` (poprawiona 24.11.2026):** Oracle sprawdza A1
  według limitu zwykłego **i** regionalnego (`standard-a1-core-count` oraz
  `standard-a1-core-regional-count`, tak samo pamięć), a `zero compute-core quotas` zeruje
  oba; polityka ustawia więc obie pary (2 rdzenie, 12 GB). Pierwsza wersja miała tylko
  zwykłe nazwy i zablokowała A1 (błąd `QuotaExceeded`, bez kosztów).
- **Tailscale, klucze serwerów:** klient OAuth z tagami może tworzyć klucze tylko
  z kompletem swoich tagów (sprawdzone 12 kombinacjami 24.11.2026), a serwer i executor
  potrzebują osobnych tagów. Rozwiązanie z dokumentacji Tailscale: tag-właściciel
  `tag:goatcash-terraform` (`tagOwners`: właściciel `tag:goatcash-server`
  i `tag:goatcash-executor`); klient `goatcash-terraform` ma tylko ten tag oraz zakresy
  Auth Keys i Devices Core (zapis).
- **Domena:** wygasa 21.11.2027; Cloudflare pokazuje odnowienie (auto-renew) 22.10.2027.
- **Wersje pakietów systemowych, obraz Ubuntu i klucze repozytoriów (decyzja właściciela
  26.11.2026, rozliczenie E3):**
  - **Pakiety apt (docker-ce, tailscale, lynis, pakiety Ubuntu) nie są przypięte do wersji.**
    **Jawne odstępstwo od zasady „przypięte wersje”** (ta obowiązuje dalej dla akcji GitHub,
    obrazów kontenerów po digeście, narzędzi z sumą SHA-256 jak sops i zależności Pythona
    w `uv.lock`). Powód: przypięte pakiety systemowe blokują poprawki bezpieczeństwa, a D6
    („Lynis 0 Warnings”, PKGS-7392) i unattended-upgrades co godzinę wymagają aktualnych
    pakietów. Ryzyko (nowa wersja coś psuje) ograniczają: `make ansible-test` na świeżym
    Ubuntu 24.04 w każdym CI, test dymny i rollback w `deploy.sh` oraz restart tylko w nocy.
  - **Obraz Ubuntu:** najnowszy „Canonical Ubuntu 24.04” dla A1 w chwili tworzenia maszyny,
    a nowszy obraz nie wymusza odtworzenia (`ignore_changes` w `compute.tf`). Aktualność daje
    `upgrade: dist` w Ansible, a powtarzalność odtworzenia potwierdza G3.
  - **Klucze repozytoriów apt są przypięte odciskiem** (to, czemu ufa apt, jest stałe):
    Docker `9DC858229FC7DD38854AE2D88D81803C0EBFCD88` (`roles/docker/defaults`), Tailscale
    `2596A99EAAB33821893C0A79458CA832957F5868` (`roles/base/defaults` i
    `cloud-init.yaml.tftpl`). Producenci nie publikują odcisków na stronach instalacji,
    więc odciski sprawdziliśmy dwoma niezależnymi kanałami (26.11.2026): pliki
    z download.docker.com i pkgs.tailscale.com (HTTPS) oraz klucze z keyserver.ubuntu.com
    mają identyczne klucze główne, podklucze i identyfikatory (Docker od 2017, Tailscale
    od 2020). Plik z innym albo dodatkowym kluczem głównym zatrzymuje Ansible, a w cloud-init
    plik jest usuwany i Tailscale się nie instaluje. Źródło apt Tailscale ma stałą treść,
    a nie plik pobrany z sieci. Sprawdza to `make ansible-test` (podmienione klucze
    i fragment cloud-init) oraz `test_repo_key_fingerprints_pinned_consistently`. Zmiana
    klucza u producenta to świadoma zmiana odcisku w repo.
- **Rozliczenie E3: odstępstwa zapisane po fakcie (26.11.2026).** Plan E3 oznaczał je jako
  zrobione, a w repo ich nie było; teraz są jawne:
  - **ACL Tailscale (plan PR 11; decyzja właściciela 26.11.2026):** źródłem prawdy jest
    konsola Tailscale, gdzie ACL ma testy (`tests`: CI tylko `tcp:22`, executor tylko
    `tcp:5432` do serwera). W repo jest kopia `infra/tailscale/acl.hujson` (eksport
    z konsoli 26.11.2026, bez sekretów i adresów e-mail), a test
    `test_tailscale_acl_copy_matches_iac` pilnuje, że tagi z Terraform, cloud-init i workflow
    są w niej zdefiniowane. Zmiana ACL: najpierw w konsoli, potem ta sama zmiana w kopii.
    ACL jako kod (provider Tailscale, zakres `policy_file`) przed produkcją, w E16.
  - **Polityka IAM executora (plan PR 8; decyzja właściciela 26.11.2026):** przeniesiona do
    **E14b**. Vault i klucz główny istnieją (`oci-trwale`), ale dziś żaden proces z nich nie
    korzysta, więc polityki (dynamic group maszyny executora i prawo użycia klucza) nie da
    się sprawdzić. Executor pierwszy raz odszyfrowuje klucze giełd w E14b (zależność „G3
    (mikro-VM, Vault)” w roadmapie) i tam polityka powstaje razem z testem.
  - **Test kopii w CI na `posix`, nie na MinIO** (plan PR 13 i tabela dowodów wyżej):
    pgBackRest (pełna, przyrostowa, WAL, szyfrowanie, PITR, sumy) sprawdzamy w CI na
    katalogu lokalnym, a ścieżkę S3 na prawdziwym R2 (`backup-now`, timery, `restore-test`
    co tydzień). MinIO dodałoby trzecią implementację S3 bez dowodu, że zachowuje się jak R2.
  - **Sekrety w stanie Terraform:** stan `observability` zawiera token bota Telegram,
    chat_id i e-mail na alerty (punkt kontaktowy Grafany), a stan `oci` jednorazowe klucze
    Tailscale (ważne 1 h, zużyte przy starcie maszyny; także w `user_data`). Klucz prywatny
    certyfikatu Origin powstaje lokalnie z CSR i w stanie go nie ma. Zabezpieczenia: bucket
    `goatcash-tfstate` jest prywatny (bez dostępu publicznego), szyfrowany przez Oracle
    w spoczynku, dostęp ma tylko użytkownik IAM `terraform` właściciela; pliki planu
    (`*.plan`, zawierają jawne wartości zmiennych) są w `.gitignore` i właściciel usuwa je
    po `apply`. Wyciek stanu = rotacja tokenu bota i Better Stack według
    `docs/runbooks/rotacja-sekretow.md`. Przed produkcją do rozważenia: osobny bucket stanu
    produkcji z kluczem z Vault.

## Rozważane alternatywy

| Opcja                                             | Za                         | Przeciw                                                                   |
| ------------------------------------------------- | -------------------------- | ------------------------------------------------------------------------- |
| Wolumen 150 GB (jak roadmapa)                     | zgodność 1:1               | ok. 250 GB dysków: opłata na koncie PAYG                                  |
| Stan Terraform na R2 (backend `s3`)               | jeden dostawca dla danych  | R2 zarządzane przez ten sam Terraform; zależność od blokady S3 w R2       |
| Stan Terraform lokalnie                           | najprościej                | brak blokady i historii; utrata dysku = utrata stanu                      |
| HCP Terraform                                     | gotowe blokady i historia  | kolejne konto i dostawca; stan poza naszą kontrolą                        |
| SSH 22 z IP właściciela                           | bez Tailscale przy starcie | port otwarty z internetu (sprzeczne z G3), zmienne IP właściciela         |
| OCI Bastion do pierwszego połączenia              | brak klucza w metadanych   | dodatkowa usługa i sesje z limitem czasu; Tailscale i tak potrzebny (E14) |
| Odtworzenie od zera w CI (klucze chmury w GitHub) | pełny dowód z CI           | klucze Oracle i Cloudflare z prawem tworzenia i usuwania w GitHub Secrets |
| G3 jako dowód w pełni lokalny (jak G0)            | bez zmian w `gate_guard`   | brak ochrony przed regresją w CI; dowody trudne do sprawdzenia            |

## Konsekwencje

- Roadmapa E3 i `testy.md` dostają przypis o wolumenie 100 GB (w PR z maszynami Terraform)
  oraz o dowodzie mieszanym (w PR z `gate_guard`).
- Limity Always Free potwierdzone 23.11.2026 (tabela w punkcie 1). Przed pierwszym
  `terraform apply` właściciel ustawia limity compartmentu; asystent przedstawia wynik
  `terraform plan` (add / change / destroy) i czeka na zgodę.
- Skrypty odtworzenia (F-01) i testu kopii (F-02) muszą przestrzegać zasady „jedna A1
  naraz” (punkt 1); sprawdza to przegląd PR z tymi skryptami.
- Nowe sprawdzenia G3 w `gates/G3.yaml` muszą wskazywać źródło dowodu z tabeli wyżej.
- STRIDE: aktualizacja wiersza administracji (SSH tylko przez Tailscale, klucz
  jednorazowy w metadanych) w PR z Ansible.
- Decyzja jest dobra, jeśli: rachunek Oracle po E3 wynosi 0 USD, `terraform plan` po
  odtworzeniu nie pokazuje zmian, a `gate_guard` odrzuca dowód G3 z podmienionym
  lub czerwonym przebiegiem (test w PR z dowodem mieszanym).
