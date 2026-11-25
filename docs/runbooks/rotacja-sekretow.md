# Runbook: rotacja sekretów staging

Kiedy: co 12 miesięcy, po odejściu osoby z dostępem, po wycieku albo podejrzeniu wycieku,
po incydencie (przed `wymiana-serwera.md`). Zasada: najpierw nowy sekret, potem przełączenie,
na końcu unieważnienie starego. Wartości nigdy w czacie ani w repo (Bitwarden, `.env.local`,
SOPS, sekrety środowisk GitHub). Komendy sprawdzające nie wypisują wartości.

| Sekret                                  | Gdzie jest                                                      | Rotacja                                                                                                                                                                                                                              |
| --------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Hasła Postgres, monitor, cipher kopii\* | `infra/secrets/staging.enc.yaml`                                | `sops infra/secrets/staging.enc.yaml`, zmiana, commit (PR), wdrożenie; hasło roli w bazie: `ALTER ROLE` przed wdrożeniem                                                                                                             |
| Klucz age `staging`                     | Bitwarden, środowisko GitHub `staging`, `/etc/goatcash/age.key` | `age-keygen` → nowy publiczny w `infra/secrets/.sops.yaml`, `sops updatekeys`, PR; sekret `SOPS_AGE_KEY_STAGING`; `ansible-staging.yml`                                                                                              |
| Klucz SSH CI (`goatcash_staging_ci`)    | Bitwarden, `STAGING_SSH_KEY` (`staging`), `infra/ssh/*.pub`     | `ssh-keygen -t ed25519`, nowy `.pub` w PR, `ansible-staging.yml` starym kluczem z nowym `.pub` (exclusive), potem sekret; nowe maszyny dostają klucz z Terraform                                                                     |
| Klucz sondy (`goatcash_staging_probe`)  | Bitwarden, `STAGING_PROBE_SSH_KEY` (`staging-readonly`), `.pub` | jak wyżej (rola `base` ustawia oba klucze naraz)                                                                                                                                                                                     |
| Token R2 kopii (zapis)                  | `staging.enc.yaml` (`postgres.PGBACKREST_REPO1_S3_KEY*`)        | Cloudflare → R2 → Manage API tokens: nowy token Object Read & Write na bucket, zmiana w SOPS, wdrożenie, `backup.sh incr` OK, usunięcie starego tokenu                                                                               |
| Token R2 testu kopii (odczyt)           | `R2_RESTORE_*` (`staging-readonly`)                             | nowy token Object Read only, sekrety, `restore-test` zielony, usunięcie starego                                                                                                                                                      |
| Klient OIDC Tailscale (CI)              | `TS_OAUTH_CLIENT_ID`, `TS_AUDIENCE` (oba środowiska)            | Tailscale → Trust credentials: nowy klient OIDC na środowisko (subject z `gh api repos/<repo>/actions/oidc/customization/sub` + `:environment:<env>`, tag `tag:goatcash-ci`), sekrety, przebieg `ansible-staging`, usunięcie starego |
| Klient OAuth Tailscale (Terraform)      | `.env.local` właściciela                                        | nowy klient (auth_keys, devices:core, tylko tag `tag:goatcash-terraform`), `.env.local`, `terraform plan` bez zmian, usunięcie starego                                                                                               |
| Token Grafana OTLP                      | `staging.enc.yaml` (`otel.GRAFANA_OTLP_TOKEN`)                  | Grafana Cloud → Access Policies: nowy token z zakresem zapisu metryk/logów/śladów, SOPS, wdrożenie, dane w pulpicie, usunięcie starego                                                                                               |
| Token ćwiczenia alertów                 | `GRAFANA_DRILL_TOKEN` (`staging`)                               | Grafana → konto serwisowe Viewer → nowy token, sekret, `alert-drill`, usunięcie starego                                                                                                                                              |
| Klucz prywatny Origin CA                | Bitwarden, `staging.enc.yaml` (`tls.ORIGIN_KEY`)                | nowy klucz i CSR (`openssl`), `infra/tls/origin.csr` w PR, `terraform apply` modułu cloudflare (nowy certyfikat), `origin.pem` w PR, klucz w SOPS, wdrożenie                                                                         |
| Bot Telegram, Better Stack, Cloudflare  | `.env.local` / zmienne Terraform właściciela                    | nowy token w konsoli dostawcy, `.env.local`, `terraform plan` modułu `observability`/`cloudflare` bez niespodzianek, unieważnienie starego                                                                                           |

\* Hasło szyfrowania kopii (`PGBACKREST_REPO1_CIPHER_PASS`) **nie** podlega zwykłej rotacji:
istniejące kopie są nim zaszyfrowane. Zmiana = nowe repozytorium kopii (nowa ścieżka
w buckecie) i pełna kopia; stare repozytorium trzymamy do końca retencji (30 dni) razem ze
starym hasłem w Bitwardenie.

## Sprawdzenie po rotacji

- `deploy-staging` (re-run) zielony, `restore-test` zielony, `external-scan` zielony.
- Stary sekret unieważniony u dostawcy (nie tylko usunięty z GitHub).
- Wpis w `docs/stan-pracy.md`: co, kiedy, dlaczego (bez wartości).
