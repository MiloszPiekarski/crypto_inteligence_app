# Pliki środowiska staging (wzór)

Na serwerze `/srv/goatcash/compose/env/*.env` powstają przy wdrożeniu z
`infra/secrets/staging.enc.yaml` (SOPS, klucz age `staging`), tryb `600`, właściciel `deploy` (skrypt `goatcash-render-env`, rola Ansible `goatcash`).
Ten katalog zawiera tylko nazwy zmiennych, bez wartości. Klucze w pliku SOPS mają postać
`<plik>.<ZMIENNA>`, np. `postgres.POSTGRES_PASSWORD`. Układ pliku (przed zaszyfrowaniem):

```yaml
postgres:
  POSTGRES_PASSWORD: …
  PGBACKREST_REPO1_S3_ENDPOINT: <account_id>.r2.cloudflarestorage.com
  # … pozostałe zmienne z tabeli
api:
  GOATCASH_DATABASE_URL: postgresql+psycopg://postgres:…@postgres:5432/postgres
api-read:
  PGPASSWORD: … # konto goatcash_api procesu api (tylko odczyt, E6)
otel: { … }
postgres-exporter: { … }
tls:
  ORIGIN_KEY: | # cała zawartość pliku klucza PEM (wiele linii)
    …
```

Tworzy go właściciel: `sops infra/secrets/staging.enc.yaml` (edytor otwiera pusty plik,
SOPS szyfruje przy zapisie kluczem age `staging` z `infra/secrets/.sops.yaml`).

| Plik                    | Zmienne                                                                                                                                          |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `postgres.env`          | `POSTGRES_PASSWORD`, `PGBACKREST_REPO1_S3_ENDPOINT`, `PGBACKREST_REPO1_S3_KEY`, `PGBACKREST_REPO1_S3_KEY_SECRET`, `PGBACKREST_REPO1_CIPHER_PASS` |
| `api.env`               | `GOATCASH_DATABASE_URL`                                                                                                                          |
| `api-read.env`          | `PGPASSWORD` (hasło konta `goatcash_api`, tylko `[0-9a-f]`; konto zakłada `ensure-api-role.sh`)                                                  |
| `otel.env`              | `GRAFANA_OTLP_ENDPOINT`, `GRAFANA_OTLP_INSTANCE_ID`, `GRAFANA_OTLP_TOKEN`                                                                        |
| `postgres-exporter.env` | `DATA_SOURCE_URI` (`postgres:5432/postgres?sslmode=disable`), `DATA_SOURCE_USER` (`goatcash_monitor`), `DATA_SOURCE_PASS`                        |

Certyfikat Cloudflare Origin CA: `/srv/goatcash/tls/origin.pem` (publiczny, z Terraform) i
`origin.key` (prywatny, z SOPS: `tls.ORIGIN_KEY`).
