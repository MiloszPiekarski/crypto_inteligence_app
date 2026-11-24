# Runbook: wymiana serwera staging (odtworzenie od zera, F-01)

Kiedy: awaria maszyny A1 lub mikro-VM, uszkodzony system, podejrzenie włamania, test
odtwarzalności G3. Wynik: nowe maszyny i wolumen danych, baza odtworzona z R2, wdrożony
bieżący `main`, w < 30 min bez ręcznych kroków (po jednym „tak”). Źródło: ADR-0007, punkty 1 i 6.

**Zasada Always Free:** w danej chwili tylko jedna A1 2/12. Skrypt najpierw usuwa starą
maszynę, potem tworzy nową; nigdy nie twórz drugiej A1 „obok”.

## Przed startem (raz)

- Klucze chmury w `.env.local` (OCI, Cloudflare, Tailscale: klient OAuth z zakresami
  `auth_keys` i `devices:core`), `gh` zalogowany, `make tools`.
- Kopie w R2 aktualne: ostatni `restore-test` zielony.
- Środowisko GitHub `staging` bez wymaganego recenzenta (inaczej Ansible i wdrożenie czekają
  na kliknięcie, czyli ręczny krok).

## Kroki

```bash
cd ~/Documents/Millosz/crypto_app
git checkout main && git pull --ff-only
set -a; . ./.env.local; set +a
./scripts/g3_rebuild.sh
```

1. Skrypt pokazuje podsumowanie `terraform plan` (zastąpienie: 2 maszyny, wolumen, załącznik,
   2 klucze Tailscale). Sprawdź, że nic poza tym nie jest usuwane, i wpisz `tak`.
2. Dalej bez udziału: stare węzły Tailscale usunięte, nowe maszyny, DNS `api.`/`app.` na nowe
   IP, zmienna `STAGING_PLATFORM_PUBLIC_IP` w `staging-readonly`, `ansible-staging.yml`,
   ponowione wdrożenie HEAD (baza z R2), `/v1/health` z internetu.
3. Ostatnia linia: `== G3 rebuild (local): PASS, <s> s, 0 manual steps ==`. Raport:
   `docs/gates/G3/rebuild-<czas>.log` (dowód G3 `rebuild`: commit w osobnym PR).
4. Po wymianie: `external-scan` i `restore-test` ręcznie (Actions → Run workflow).

## Podejrzenie włamania

Przed wymianą: zrotuj sekrety według `rotacja-sekretow.md` (klucz SSH CI, klucz sondy,
klucz age staging, token R2, hasła baz). Nowy serwer dostaje nowe klucze z nowego
`staging.enc.yaml`. Kopie sprzed incydentu odtwarzaj do czasu sprzed włamania (PITR,
`odtworzenie-z-kopii.md`, część C).

## Gdy coś nie działa

- `terraform apply` odrzuca A1 („Out of host capacity”): region chwilowo bez A1; ponów
  później (nie zmieniaj kształtu bez decyzji kosztowej).
- Węzły nie pojawiają się w Tailscale: konsola szeregowa OCI → `cloud-init status --long`
  i `journalctl -u tailscaled`; klucz jednorazowy wygasa po 1 h (ponów skrypt).
- `ansible-staging.yml` czerwony: popraw rolę, ponów workflow, potem `gh run rerun` wdrożenia.
