#!/usr/bin/env bash
# scripts/sops_staging_init.sh: tworzy infra/secrets/staging.enc.yaml (SOPS, klucz age staging)
# bez sekretów w czacie, w historii powłoki ani w repo w postaci jawnej.
#   1. generuje hasła (Postgres, rola monitora, szyfrowanie kopii pgBackRest): tylko [0-9a-f],
#      bo pliki .env są czytane przez Compose i przez `.` w ensure-roles.sh;
#   2. otwiera wzór w edytorze ($EDITOR, domyślnie nano) w katalogu tymczasowym (0700);
#      właściciel wkleja w miejsca WSTAW_… tokeny R2 i dane Grafana OTLP (jednolinijkowe);
#   3. klucz prywatny Origin CA (wielolinijkowy PEM) bierze ze schowka (pbpaste) i wstawia
#      sam, potem czyści schowek; ręczne wcinanie PEM w edytorze kończyło się błędem YAML;
#   4. sprawdza kompletność (bez wypisywania wartości), szyfruje regułą z
#      infra/secrets/.sops.yaml, ustawia sekret PGBACKREST_CIPHER_PASS w środowisku GitHub
#      staging-readonly (gh) i usuwa wersję jawną.
# Istniejącego pliku nie nadpisuje (zmiany: `sops infra/secrets/staging.enc.yaml`).
# Użycie: ./scripts/sops_staging_init.sh   (sops z `make tools`, czyli .tools/bin).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [ -d .tools/bin ]; then PATH="$PWD/.tools/bin:$PATH"; fi
OUT="${GOATCASH_SOPS_OUT:-infra/secrets/staging.enc.yaml}"
PASTE="${GOATCASH_PASTE_CMD:-pbpaste}"
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
# Wypełnij każde pole zaczynające się od WSTAW: wklej wartość między cudzysłowy w miejsce
# całego słowa. Zapisz (Ctrl+O, Enter) i zamknij (Ctrl+X). Linie z # zostaną pominięte.
# Hasła są już wygenerowane: nie zmieniaj. Klucz Origin CA skrypt weźmie później ze schowka.
postgres:
  POSTGRES_PASSWORD: "$PG"
  # R2: token goatcash-pgbackrest (Object Read & Write). Endpoint BEZ https://,
  # np. <account_id>.r2.cloudflarestorage.com (bucket bez jurysdykcji UE: bez .eu.)
  PGBACKREST_REPO1_S3_ENDPOINT: "WSTAW_R2_ENDPOINT"
  PGBACKREST_REPO1_S3_KEY: "WSTAW_R2_ACCESS_KEY_ID"
  PGBACKREST_REPO1_S3_KEY_SECRET: "WSTAW_R2_SECRET_ACCESS_KEY"
  PGBACKREST_REPO1_CIPHER_PASS: "$(gen)"
api:
  GOATCASH_DATABASE_URL: "postgresql+psycopg://postgres:$PG@postgres:5432/postgres"
otel:
  # Grafana Cloud: endpoint OTLP Z https:// (kończy się na /otlp), Instance ID, token.
  GRAFANA_OTLP_ENDPOINT: "WSTAW_GRAFANA_OTLP_ENDPOINT"
  GRAFANA_OTLP_INSTANCE_ID: "WSTAW_GRAFANA_INSTANCE_ID"
  GRAFANA_OTLP_TOKEN: "WSTAW_GRAFANA_OTLP_TOKEN"
postgres-exporter:
  DATA_SOURCE_URI: "postgres:5432/postgres?sslmode=disable"
  DATA_SOURCE_USER: "goatcash_monitor"
  DATA_SOURCE_PASS: "$(gen)"
EOF

"${EDITOR:-nano}" "$PLAIN"

# Komentarze z wzoru nie trafiają do pliku (SOPS zostawia komentarze jawne) ani do kontroli.
CLEAN="$TMP/clean.yaml"
grep -v '^[[:space:]]*#' "$PLAIN" > "$CLEAN" || true
if grep -q 'WSTAW_' "$CLEAN"; then
  echo "Zostały niewypełnione pola:"; grep -o 'WSTAW_[A-Z0-9_]*' "$CLEAN" | sort -u | sed 's/^/  /'
  echo "Nic nie zapisano. Uruchom skrypt jeszcze raz."; exit 1
fi

echo
echo "Skopiuj z Bitwardena CAŁY klucz prywatny Origin CA (od -----BEGIN do -----END)"
printf "do schowka, potem naciśnij Enter: "
read -r _ < /dev/tty || true
"$PASTE" > "$TMP/origin.key"
# Schowek czyszczony tylko przy prawdziwym pbpaste (testy podają własne polecenie).
if [ "$PASTE" = pbpaste ]; then pbcopy < /dev/null; fi

# Kontrola i złożenie (bez wypisywania wartości): składnia, wymagane pola, PEM, adresy.
FINAL="$TMP/final.yaml"
uv run --frozen python - "$CLEAN" "$TMP/origin.key" "$FINAL" "$TMP/cipher" <<'PY'
import sys, yaml
clean, key_path, final, cipher = sys.argv[1:5]
try:
    data = yaml.safe_load(open(clean, encoding="utf-8")) or {}
except yaml.YAMLError as exc:
    mark = getattr(exc, "problem_mark", None)
    where = f" (linia {mark.line + 1})" if mark else ""
    print(f"Błąd składni YAML{where}: sprawdź cudzysłowy wokół wklejonej wartości.")
    sys.exit(1)
key = open(key_path, encoding="utf-8").read().strip()
data["tls"] = {"ORIGIN_KEY": key + "\n"}
want = {
    "postgres": ["POSTGRES_PASSWORD", "PGBACKREST_REPO1_S3_ENDPOINT", "PGBACKREST_REPO1_S3_KEY",
                 "PGBACKREST_REPO1_S3_KEY_SECRET", "PGBACKREST_REPO1_CIPHER_PASS"],
    "api": ["GOATCASH_DATABASE_URL"],
    "otel": ["GRAFANA_OTLP_ENDPOINT", "GRAFANA_OTLP_INSTANCE_ID", "GRAFANA_OTLP_TOKEN"],
    "postgres-exporter": ["DATA_SOURCE_URI", "DATA_SOURCE_USER", "DATA_SOURCE_PASS"],
}
bad = [f"{f}.{k}" for f, ks in want.items() for k in ks
       if not isinstance((data.get(f) or {}).get(k), (str, int)) or not str(data[f][k]).strip()]
if not (key.startswith("-----BEGIN") and key.endswith("PRIVATE KEY-----") and "PRIVATE KEY" in key.splitlines()[0]):
    bad.append("klucz Origin CA ze schowka (to nie jest blok PEM klucza prywatnego)")
ep = str((data.get("postgres") or {}).get("PGBACKREST_REPO1_S3_ENDPOINT", ""))
if "://" in ep:
    bad.append("postgres.PGBACKREST_REPO1_S3_ENDPOINT (bez https://)")
if not str((data.get("otel") or {}).get("GRAFANA_OTLP_ENDPOINT", "")).startswith("https://"):
    bad.append("otel.GRAFANA_OTLP_ENDPOINT (musi zaczynać się od https://)")
if bad:
    print("Niepoprawne pola: " + ", ".join(bad) + ". Nic nie zapisano.")
    sys.exit(1)
for section in want:
    data[section] = {k: str(v) for k, v in data[section].items()}
with open(final, "w", encoding="utf-8") as fh:
    yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True, width=10000)
with open(cipher, "w", encoding="utf-8") as fh:
    fh.write(data["postgres"]["PGBACKREST_REPO1_CIPHER_PASS"])
PY

sops --config infra/secrets/.sops.yaml --encrypt --filename-override infra/secrets/staging.enc.yaml \
  --input-type yaml --output-type yaml "$FINAL" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
echo "Zapisano $OUT (zaszyfrowany kluczem age staging)."

# Hasło szyfrowania kopii potrzebuje też restore-test.yml (środowisko staging-readonly):
# prosto z pliku tymczasowego do sekretu GitHub, bez wyświetlania.
if [ "${GOATCASH_SKIP_GH:-0}" != 1 ]; then
  if gh secret set PGBACKREST_CIPHER_PASS --env staging-readonly < "$TMP/cipher"; then
    echo "Ustawiono sekret PGBACKREST_CIPHER_PASS w środowisku staging-readonly."
  else
    echo "UWAGA: nie udało się ustawić sekretu PGBACKREST_CIPHER_PASS (gh); plik SOPS jest zapisany."
  fi
fi
echo "Wersja jawna usunięta (katalog tymczasowy)."
