#!/usr/bin/env bash
# scripts/sops_staging_init.sh: tworzy infra/secrets/staging.enc.yaml (SOPS, klucz age staging)
# bez sekretów w czacie, w historii powłoki ani w repo w postaci jawnej.
#   1. generuje hasła (Postgres, rola monitora, szyfrowanie kopii pgBackRest): tylko [0-9a-f],
#      bo pliki .env są czytane przez Compose i przez `.` w ensure-roles.sh;
#   2. otwiera wzór w edytorze ($EDITOR, domyślnie nano) w katalogu tymczasowym (0700);
#      właściciel wkleja w miejsca WSTAW_… tokeny R2, dane Grafana OTLP i klucz Origin CA;
#   3. sprawdza, że nie zostało żadne WSTAW_ ani pusta wartość, szyfruje regułą
#      z infra/secrets/.sops.yaml i usuwa wersję jawną.
# Istniejącego pliku nie nadpisuje (zmiany: `sops infra/secrets/staging.enc.yaml`).
# Na końcu ustawia sekret PGBACKREST_CIPHER_PASS w środowisku GitHub staging-readonly (gh).
# Użycie: ./scripts/sops_staging_init.sh   (sops z `make tools`, czyli .tools/bin).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [ -d .tools/bin ]; then PATH="$PWD/.tools/bin:$PATH"; fi
OUT="${GOATCASH_SOPS_OUT:-infra/secrets/staging.enc.yaml}"
command -v sops >/dev/null || { echo "Brak sops (uruchom: make tools)"; exit 1; }
[ ! -e "$OUT" ] || { echo "$OUT już istnieje; zmiany: sops $OUT"; exit 1; }

TMP="$(mktemp -d)"
chmod 700 "$TMP"
trap 'rm -rf "$TMP"' EXIT
PLAIN="$TMP/staging.yaml"
gen() { openssl rand -hex 24; }
PG="$(gen)"
umask 077
cat > "$PLAIN" <<EOF
# Wypełnij każde pole zaczynające się od WSTAW (wklej wartość w miejsce całego słowa), zapisz i zamknij edytor.
# Linie zaczynające się od # zostaną pominięte. Hasła niżej są już wygenerowane: nie zmieniaj.
postgres:
  POSTGRES_PASSWORD: "$PG"
  # R2 → Manage API tokens → token „goatcash-pgbackrest” (Object Read & Write, bucket
  # goatcash-staging-backups). Endpoint bez https://, np. <account_id>.eu.r2.cloudflarestorage.com
  PGBACKREST_REPO1_S3_ENDPOINT: "WSTAW_R2_ENDPOINT"
  PGBACKREST_REPO1_S3_KEY: "WSTAW_R2_ACCESS_KEY_ID"
  PGBACKREST_REPO1_S3_KEY_SECRET: "WSTAW_R2_SECRET_ACCESS_KEY"
  PGBACKREST_REPO1_CIPHER_PASS: "$(gen)"
api:
  GOATCASH_DATABASE_URL: "postgresql+psycopg://postgres:$PG@postgres:5432/postgres"
otel:
  # Grafana Cloud → stos → OpenTelemetry → Configure: endpoint OTLP (https://…/otlp),
  # Instance ID (liczba) i token (zakresy zapisu metryk, logów i śladów).
  GRAFANA_OTLP_ENDPOINT: "WSTAW_GRAFANA_OTLP_ENDPOINT"
  GRAFANA_OTLP_INSTANCE_ID: "WSTAW_GRAFANA_INSTANCE_ID"
  GRAFANA_OTLP_TOKEN: "WSTAW_GRAFANA_OTLP_TOKEN"
postgres-exporter:
  DATA_SOURCE_URI: "postgres:5432/postgres?sslmode=disable"
  DATA_SOURCE_USER: "goatcash_monitor"
  DATA_SOURCE_PASS: "$(gen)"
tls:
  # Klucz prywatny Origin CA z Bitwardena (cały blok PEM, z liniami BEGIN/END), wcięty
  # o 4 spacje pod tą linią, w miejsce słowa poniżej.
  ORIGIN_KEY: |
    WSTAW_ORIGIN_KEY
EOF

"${EDITOR:-nano}" "$PLAIN"

# Komentarze z wzoru nie trafiają do pliku (SOPS zostawia komentarze jawne) ani do kontroli.
CLEAN="$TMP/clean.yaml"
grep -v '^[[:space:]]*#' "$PLAIN" > "$CLEAN" || true
if grep -q 'WSTAW_' "$CLEAN"; then
  echo "Zostały niewypełnione pola:"; grep -o 'WSTAW_[A-Z0-9_]*' "$CLEAN" | sort -u | sed 's/^/  /'
  echo "Nic nie zapisano. Uruchom skrypt jeszcze raz."; exit 1
fi
# Kontrola struktury (bez wypisywania wartości): wymagane klucze, niepuste napisy, PEM klucza.
uv run --frozen python - "$CLEAN" <<'PY'
import sys, yaml
want = {
    "postgres": ["POSTGRES_PASSWORD", "PGBACKREST_REPO1_S3_ENDPOINT", "PGBACKREST_REPO1_S3_KEY",
                 "PGBACKREST_REPO1_S3_KEY_SECRET", "PGBACKREST_REPO1_CIPHER_PASS"],
    "api": ["GOATCASH_DATABASE_URL"],
    "otel": ["GRAFANA_OTLP_ENDPOINT", "GRAFANA_OTLP_INSTANCE_ID", "GRAFANA_OTLP_TOKEN"],
    "postgres-exporter": ["DATA_SOURCE_URI", "DATA_SOURCE_USER", "DATA_SOURCE_PASS"],
    "tls": ["ORIGIN_KEY"],
}
data = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
bad = [f"{f}.{k}" for f, ks in want.items() for k in ks
       if not isinstance((data.get(f) or {}).get(k), str) or not data[f][k].strip()]
key = (data.get("tls") or {}).get("ORIGIN_KEY", "")
if "PRIVATE KEY-----" not in key:
    bad.append("tls.ORIGIN_KEY (brak bloku PEM)")
if "://" in data["postgres"]["PGBACKREST_REPO1_S3_ENDPOINT"]:
    bad.append("postgres.PGBACKREST_REPO1_S3_ENDPOINT (bez https://)")
if not data["otel"]["GRAFANA_OTLP_ENDPOINT"].startswith("https://"):
    bad.append("otel.GRAFANA_OTLP_ENDPOINT (musi zaczynać się od https://)")
if bad:
    print("Niepoprawne pola: " + ", ".join(bad)); sys.exit(1)
PY

sops --config infra/secrets/.sops.yaml --encrypt --filename-override infra/secrets/staging.enc.yaml \
  --input-type yaml --output-type yaml "$CLEAN" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
echo "Zapisano $OUT (zaszyfrowany kluczem age staging)."

# Hasło szyfrowania kopii potrzebuje też restore-test.yml (środowisko staging-readonly):
# prosto z pliku tymczasowego do sekretu GitHub, bez wyświetlania.
if [ "${GOATCASH_SKIP_GH:-0}" != 1 ]; then
  uv run --frozen python -c 'import sys, yaml; sys.stdout.write(yaml.safe_load(open(sys.argv[1]))["postgres"]["PGBACKREST_REPO1_CIPHER_PASS"])' \
    "$CLEAN" > "$TMP/cipher"
  gh secret set PGBACKREST_CIPHER_PASS --env staging-readonly < "$TMP/cipher" &&
    echo "Ustawiono sekret PGBACKREST_CIPHER_PASS w środowisku staging-readonly." ||
    echo "UWAGA: nie udało się ustawić sekretu PGBACKREST_CIPHER_PASS (gh); plik SOPS jest zapisany."
fi
echo "Wersja jawna zostanie usunięta."
