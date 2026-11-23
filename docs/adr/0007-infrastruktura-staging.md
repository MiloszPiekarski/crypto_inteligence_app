# ADR-0007: Infrastruktura staging: budżet zasobów, stan Terraform, dostęp i dowód G3

- **Status:** proponowana (decyzje D2–D6 zaakceptowane przez właściciela 23.11.2026;
  zatwierdzenie całości scaleniem PR)
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

| Zasób                                | Ilość                     | Uwagi                                   |
| ------------------------------------ | ------------------------- | --------------------------------------- |
| VM Ampere A1 (arm64)                 | 1 × 2 OCPU / 12 GB        | roadmapa E3; serwer platformy           |
| VM AMD `VM.Standard.E2.1.Micro`      | 1                         | executor (ADR-0006), zarezerwowane IP   |
| Dysk startowy A1                     | 50 GB                     | minimum dysku startowego OCI to 50 GB   |
| Dysk startowy mikro-VM               | 50 GB                     |                                         |
| Wolumen danych A1 (Postgres, Valkey) | **100 GB** (roadmapa 150) | **jawne odstępstwo**, patrz niżej       |
| Razem dyski                          | 200 GB                    | limit Always Free dla dysków (do potw.) |
| Object Storage (stan Terraform)      | < 1 GB                    | bucket z wersjonowaniem                 |
| OCI Vault                            | 1 klucz główny (AES)      | ADR-0006; wariant bez opłat (do potw.)  |

**Odstępstwo od roadmapy:** wolumen danych 100 GB zamiast 150 GB. Przy 150 GB dyski
razem miałyby ok. 250 GB i przekroczyły limit Always Free, co na koncie PAYG oznacza
opłatę. Kopie trafiają na R2 (nie na dysk), a dane rynkowe pojawią się dopiero w E4, więc
100 GB wystarcza na E3–E5; alert dysku > 80% (F-03) ostrzeże z wyprzedzeniem. Zwiększenie
wolumenu w przyszłości to zmiana jednej wartości w Terraform i jawna decyzja kosztowa.

**Źródła i to, czego nie udało się potwierdzić automatycznie:** dokumentacja OCI
(„Getting Started with OCI Ampere A1 Compute for Free”: pierwsze 3000 OCPU-godzin
i 18 000 GB-godzin A1 miesięcznie bez opłat; „Oracle Cloud Infrastructure Free Tier”:
konto Always Free do 2 OCPU i 12 GB A1; „Creating an Instance”: dysk startowy od 50 GB).
Strona z listą zasobów Always Free (limit 200 GB dysków, mikro-VM, Object Storage, Vault)
zwraca automatom 404/403; **właściciel potwierdza te limity w konsoli lub na stronie Oracle
przed pierwszym `terraform apply`** (wynik zapisujemy w raporcie `G3.md`).

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

| Sprawdzenie                                                                                  | Gdzie działa                                                  | Dowód                                       |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------- |
| Statyczne (fmt/validate, tflint, ansible-lint, Compose, testy skryptów, test kopii na MinIO) | CI (`ci.yml`, job bramki G3)                                  | ID przebiegu na `main` (jak G1, G2)         |
| Wdrożenie z testem dymnym i rollbackiem                                                      | `deploy-staging.yml` na `main`                                | ID przebiegu, sprawdzany przez `gate-guard` |
| Test odtworzenia kopii (F-02, tygodniowy)                                                    | workflow z harmonogramem                                      | ID przebiegu, sprawdzany przez `gate-guard` |
| Skan z zewnątrz (nmap) i Lynis                                                               | workflow na runnerze GitHub (Tailscale do Lynis)              | ID przebiegu                                |
| Alerty < 5 min (dysk, zatrzymany kontener)                                                   | workflow ćwiczenia alertów (cel); w razie braku API: lokalnie | ID przebiegu albo raport lokalny            |
| Odtworzenie środowiska od zera < 30 min (F-01)                                               | komputer właściciela (klucze chmury)                          | raport lokalny z czasem, bez sekretów       |

`gate_guard` dostaje nowy typ dowodu `mixed`: przebieg `ci.yml` na `main` plus lista ID
przebiegów nazwanych workflow (każdy: zielony, `main`, ten sam commit albo nowszy niż
wskazany) plus raporty lokalne z sumą SHA-256 zapisaną w pliku dowodu. Zmiana `gate_guard`
to osobny PR z testami obejścia i niezależnym recenzentem (ryzyko: `pull_request_target`).
Raport lokalny jest oświadczeniem właściciela (jak G0), dlatego ograniczamy go do jednego
sprawdzenia, którego nie da się bezpiecznie przenieść do CI (klucze Oracle i Cloudflare
zostają na komputerze właściciela).

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
- Przed pierwszym `terraform apply` właściciel potwierdza limity Always Free i ustawia
  limity compartmentu; asystent przedstawia wynik `terraform plan` (add / change / destroy)
  i czeka na zgodę.
- Nowe sprawdzenia G3 w `gates/G3.yaml` muszą wskazywać źródło dowodu z tabeli wyżej.
- STRIDE: aktualizacja wiersza administracji (SSH tylko przez Tailscale, klucz
  jednorazowy w metadanych) w PR z Ansible.
- Decyzja jest dobra, jeśli: rachunek Oracle po E3 wynosi 0 USD, `terraform plan` po
  odtworzeniu nie pokazuje zmian, a `gate_guard` odrzuca dowód G3 z podmienionym
  lub czerwonym przebiegiem (test w PR z dowodem mieszanym).
