#!/usr/bin/env bash
# make compose-staging-test (bramka G3 `compose-staging`): cały stos staging z
# infra/compose/staging na lokalnym Dockerze, wdrożony PRAWDZIWYM deploy.sh:
#   1. wdrożenie obrazu platformy zbudowanego z repo: migracje, healthchecki, test dymny przez
#      Caddy (TLS), stanza pgBackRest i kopia (repozytorium lokalne zamiast R2);
#   2. Postgres 17 z TimescaleDB i pgvector, Valkey z AOF, eksportery odpowiadają, metryka kopii;
#   3. wdrożenie celowo zepsutego obrazu: deploy.sh kończy się błędem i wraca do poprzedniego
#      obrazu (automatyczny rollback), a /v1/health dalej odpowiada;
#   4. nowy serwer (F-01): wolumen bazy usunięty, deploy.sh odtwarza bazę z kopii (repozytorium
#      kopii poza wolumenem bazy, jak R2) i dane sprzed kopii są na miejscu.
# Telemetria idzie na nieistniejący adres (bez kluczy Grafana w CI); kolektor ma być zdrowy.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
WORK="$(mktemp -d)"
PROJECT="g3cs$$"
GOOD="sha-0000000000000000000000000000000000000001"
BAD="sha-0000000000000000000000000000000000000002"
REPO_IMAGE="ghcr.io/miloszpiekarski/goatcash-platform"
PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"
fail() { echo "  FAIL $*" >&2; exit 1; }
ok() { echo "  PASS $*"; }

cp -R infra/compose/staging "$WORK/compose"
mkdir -p "$WORK/tls" "$WORK/metrics" "$WORK/compose/env" "$WORK/repo"
chmod 0777 "$WORK/metrics" "$WORK/repo"
# Repozytorium kopii poza wolumenem bazy (na serwerze: R2), żeby przeżyło usunięcie wolumenu.
printf 'services:\n  postgres:\n    volumes:\n      - %s:/test-repo\n' "$WORK/repo" > "$WORK/compose/compose.override.yaml"
export COMPOSE_PROJECT_NAME="$PROJECT" GOATCASH_HTTPS_PORT="$PORT" GOATCASH_TLS_DIR="$WORK/tls" \
  GOATCASH_METRICS_DIR="$WORK/metrics" GOATCASH_SKIP_PULL=1
dc() { (cd "$WORK/compose" && GOATCASH_IMAGE_TAG="${TAG:-$GOOD}" docker compose "$@"); }
cleanup() {
  dc down -v --remove-orphans >/dev/null 2>&1 || true
  docker image rm "$REPO_IMAGE:$GOOD" "$REPO_IMAGE:$BAD" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

echo "== przygotowanie: obraz platformy z repo, certyfikat testowy, pliki środowiska"
docker build -q -f services/platform/Dockerfile -t "$REPO_IMAGE:$GOOD" . >/dev/null
# Zepsuty obraz: bez serwera HTTP (api nie przejdzie healthchecku).
printf 'FROM %s\nUSER root\nRUN rm /app/.venv/bin/uvicorn\nUSER goatcash\n' "$REPO_IMAGE:$GOOD" |
  docker build -q -t "$REPO_IMAGE:$BAD" - >/dev/null
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=api.goatcash.app" \
  -addext "subjectAltName=DNS:api.goatcash.app,DNS:app.goatcash.app" \
  -keyout "$WORK/tls/origin.key" -out "$WORK/tls/origin.pem" >/dev/null 2>&1
chmod 0644 "$WORK/tls/origin.key"
PW="pg-$(date +%s)"
cat > "$WORK/compose/env/postgres.env" <<EOF
POSTGRES_PASSWORD=$PW
PGBACKREST_REPO1_TYPE=posix
PGBACKREST_REPO1_PATH=/test-repo
PGBACKREST_REPO1_CIPHER_PASS=cipher-$$
EOF
echo "GOATCASH_DATABASE_URL=postgresql+psycopg://postgres:$PW@postgres:5432/postgres" > "$WORK/compose/env/api.env"
printf 'GRAFANA_OTLP_ENDPOINT=http://127.0.0.1:9\nGRAFANA_OTLP_INSTANCE_ID=0\nGRAFANA_OTLP_TOKEN=test\n' > "$WORK/compose/env/otel.env"
printf 'DATA_SOURCE_URI=postgres:5432/postgres?sslmode=disable\nDATA_SOURCE_USER=goatcash_monitor\nDATA_SOURCE_PASS=mon-%s\n' "$$" \
  > "$WORK/compose/env/postgres-exporter.env"
ok "obraz $GOOD, zepsuty $BAD, certyfikat i pliki .env"

echo "== wdrożenie deploy.sh $GOOD"
"$WORK/compose/deploy.sh" "$GOOD" > "$WORK/deploy1.log" 2>&1 || { tail -40 "$WORK/deploy1.log" >&2; fail "deploy.sh $GOOD"; }
grep -q "test dymny: OK" "$WORK/deploy1.log" || fail "brak testu dymnego w deploy.sh"
[ "$(cat "$WORK/compose/.image-tag")" = "$GOOD" ] || fail ".image-tag po wdrożeniu"
ok "deploy.sh: migracje, healthchecki, test dymny przez Caddy (TLS)"

for s in postgres valkey api caddy otel-collector; do
  state="$(docker inspect -f '{{.State.Health.Status}}' "$(dc ps -q "$s")")"
  [ "$state" = healthy ] || fail "usługa $s: $state"
done
ok "healthchecki: postgres, valkey, api, caddy, otel-collector"

exts="$(dc exec -T postgres psql -U postgres -tAc "SELECT string_agg(extname, ',' ORDER BY extname) FROM pg_extension WHERE extname IN ('timescaledb','vector')")"
ver="$(dc exec -T postgres psql -U postgres -tAc "SHOW server_version_num")"
[ "$exts" = "timescaledb,vector" ] && [ "${ver:0:2}" = 17 ] || fail "Postgres: wersja $ver, rozszerzenia '$exts'"
ok "Postgres 17 z timescaledb i vector"
aof="$(dc exec -T valkey valkey-cli CONFIG GET appendonly | tail -1)"
[ "$aof" = yes ] || fail "Valkey appendonly=$aof"
ok "Valkey: AOF włączony"

dc exec -T postgres psql -U postgres -qc "CREATE TABLE g3_marker AS SELECT 'przed-kopia'::text AS v" >/dev/null
(cd "$WORK/compose" && TAG="$GOOD" ./backup.sh full > "$WORK/backup.log" 2>&1) || { tail -20 "$WORK/backup.log" >&2; fail "backup.sh full"; }
ok "backup.sh full (pgBackRest, szyfrowanie, archiwum WAL)"

metrics() { dc exec -T api python -c "import urllib.request,sys; sys.stdout.write(urllib.request.urlopen('http://$1/metrics', timeout=5).read().decode())"; }
# Wynik najpierw do zmiennej: `cmd | grep -q` z pipefail pada przez SIGPIPE (lekcja z E3).
sleep 2
NODE="$(metrics node-exporter:9100)"; PGX="$(metrics postgres-exporter:9187)"; VKX="$(metrics valkey-exporter:9121)"
grep -q '^goatcash_backup_last_success_timestamp_seconds{type="full"}' <<<"$NODE" || fail "brak metryki kopii w node-exporter"
grep -q '^node_filesystem_avail_bytes' <<<"$NODE" || fail "brak metryk dysku"
grep -q '^pg_up 1' <<<"$PGX" || fail "postgres-exporter: pg_up != 1"
grep -q '^redis_up 1' <<<"$VKX" || fail "valkey-exporter: redis_up != 1"
ok "eksportery: dysk, metryka kopii, pg_up 1, redis_up 1"

echo "== rollback: wdrożenie zepsutego obrazu $BAD"
if "$WORK/compose/deploy.sh" "$BAD" > "$WORK/deploy2.log" 2>&1; then fail "deploy.sh zepsutego obrazu zakończył się sukcesem"; fi
grep -q "ROLLBACK do $GOOD" "$WORK/deploy2.log" || { tail -30 "$WORK/deploy2.log" >&2; fail "brak rollbacku"; }
[ "$(cat "$WORK/compose/.image-tag")" = "$GOOD" ] || fail ".image-tag po rollbacku"
running="$(docker inspect -f '{{.Config.Image}}' "$(dc ps -q api)")"
[ "$running" = "$REPO_IMAGE:$GOOD" ] || fail "po rollbacku działa $running"
HEALTH="$(curl -fsS -k --resolve "api.goatcash.app:$PORT:127.0.0.1" "https://api.goatcash.app:$PORT/v1/health")" || fail "/v1/health po rollbacku"
grep -q '"status":"ok"' <<<"$HEALTH" || fail "/v1/health po rollbacku: $HEALTH"
ok "zepsuty obraz: deploy.sh kod błędu, automatyczny powrót do $GOOD, /v1/health ok"

echo "== nowy serwer: pusty wolumen bazy, odtworzenie z kopii w deploy.sh"
dc down >/dev/null 2>&1
docker volume rm "${PROJECT}_pgdata" >/dev/null || fail "usunięcie wolumenu bazy"
"$WORK/compose/deploy.sh" "$GOOD" > "$WORK/deploy3.log" 2>&1 || { tail -40 "$WORK/deploy3.log" >&2; fail "deploy.sh na pustym wolumenie"; }
grep -q "odtworzenie z kopii: OK" "$WORK/deploy3.log" || { tail -30 "$WORK/deploy3.log" >&2; fail "deploy.sh nie odtworzył bazy z kopii"; }
marker="$(dc exec -T postgres psql -U postgres -tAc "SELECT v FROM g3_marker")"
[ "$marker" = przed-kopia ] || fail "po odtworzeniu brak danych sprzed kopii ('$marker')"
ok "pusty wolumen: deploy.sh odtworzył bazę z kopii, dane na miejscu, test dymny OK"
echo "compose-staging-test: OK"
