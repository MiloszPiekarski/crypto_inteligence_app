# Runbook: odtworzenie bazy staging z kopii (pgBackRest, R2)

Kiedy: utrata albo uszkodzenie danych Postgresa na staging, błędna migracja, której nie da
się cofnąć, test odtworzenia (F-02) na żądanie. Źródło: ADR-0007, punkty 1 i 6.

Kopie: bucket R2 `goatcash-staging-backups` (EEUR), ścieżka `/staging`, stanza `goatcash`,
szyfrowanie aes-256-cbc (hasło w `staging.enc.yaml`, klucz `postgres.PGBACKREST_REPO1_CIPHER_PASS`
i w Bitwardenie), pełna kopia w niedzielę, przyrostowa w pozostałe dni (02:30 UTC, timery
`goatcash-backup-{full,incr}.timer`), WAL co najwyżej 5 min (`archive_timeout` 300 s),
retencja 30 dni. RPO: 5 min; RTO: kilka minut dla obecnych rozmiarów (mierzy `restore-test`).

## A. Sprawdzenie bez dotykania serwera (zalecane najpierw)

GitHub → Actions → **restore-test** → Run workflow (gałąź `main`). Wynik: odtworzenie
najnowszej kopii + WAL do świeżego punktu przywracania na runnerze i porównanie sum
wszystkich tabel. Zielony przebieg = kopie są kompletne i odszyfrowywalne.

## B. Odtworzenie najnowszego stanu na tym samym serwerze

Działa automatycznie: pusty wolumen bazy + kopia w R2 → `deploy.sh` odtwarza bazę przed
startem (`restore_if_empty`). Kroki (właściciel, przez Tailscale z komputera, który ma
Tailscale, albo przez konsolę szeregową OCI):

1. Zatrzymaj stos i usuń **tylko** wolumen bazy (nieodwracalne dla danych lokalnych; kopia
   w R2 zostaje):

   ```bash
   cd /srv/goatcash/compose && export GOATCASH_IMAGE_TAG="$(cat .image-tag)"
   docker compose down
   docker volume rm goatcash_pgdata
   ```
2. Wdróż ponownie bieżący obraz: GitHub → Actions → ostatni zielony **deploy-staging** →
   Re-run all jobs. W logu: `odtworzenie z kopii: OK`, potem `test dymny: OK`.
3. Sprawdź: `restore-test` (punkt A) i pulpit Postgres w Grafanie.

## C. Odtworzenie do punktu w czasie (PITR)

Gdy trzeba wrócić przed błędną zmianę (np. `2026-12-01 10:15:00+00`):

```bash
cd /srv/goatcash/compose && export GOATCASH_IMAGE_TAG="$(cat .image-tag)"
docker compose stop api postgres
docker compose run --rm --no-deps -T --entrypoint pgbackrest postgres \
  --stanza=goatcash --delta restore --type=time --target="2026-12-01 10:15:00+00" \
  --target-action=promote
docker compose up -d --wait
```

Po PITR baza zaczyna nową oś czasu (timeline); pgBackRest archiwizuje ją dalej. Zrób od razu
pełną kopię: GitHub → Actions → **backup-now** → Run workflow (bez Tailscale na komputerze)
albo na serwerze `sudo systemctl start goatcash-backup@full.service`.

## D. Kopia na żądanie

GitHub → Actions → **backup-now** → Run workflow (`main`): pełna kopia tym samym skryptem co
timer (`backup.sh full`), metryka wieku kopii odświeża się w Grafanie. Przed ryzykowną zmianą,
przed odtworzeniem od zera i na świeżym serwerze przed pierwszą kopią z timera (02:30 UTC).

## Gdy coś nie działa

- `stanza-create` odrzuca bazę („does not match the database”): baza nie pochodzi z tej
  stanzy. Nie usuwaj stanzy w R2; odtwórz według B.
- Brak WAL do wskazanego czasu: wybierz wcześniejszy punkt (`pgbackrest info` pokazuje zakres
  archiwum).
- Błąd odszyfrowania: sprawdź hasło szyfrowania w Bitwardenie z wpisem w `staging.enc.yaml`
  (bez wypisywania wartości: `sops -d … | grep -c CIPHER_PASS`).
