#!/usr/bin/env bash
# scripts/restore_from_r2.sh PUNKT SUMY.json: odtworzenie kopii staging z R2 do czystej instancji
# (restore-test.yml, dowód G3 `restore-test`, F-02). PUNKT to nazwany punkt przywracania, który
# sonda na serwerze utworzyła zaraz po policzeniu SUM (goatcash-probe restore-point).
#   1. pgBackRest odtwarza najnowszą kopię + WAL do PUNKTU (PITR) do pustego wolumenu;
#   2. Postgres startuje BEZ archiwizacji WAL (odtworzona instancja nie pisze do repozytorium);
#   3. sumy kontrolne wszystkich tabel (scripts/pg_checksums.py) muszą być identyczne z SUMAMI.
# Dostęp do R2 (token tylko do odczytu) i hasło szyfrowania kopii: zmienne
# PGBACKREST_REPO1_S3_ENDPOINT, PGBACKREST_REPO1_S3_KEY, PGBACKREST_REPO1_S3_KEY_SECRET,
# PGBACKREST_REPO1_CIPHER_PASS (sekrety środowiska staging-readonly).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
POINT="${1:?Użycie: restore_from_r2.sh PUNKT SUMY.json}"
EXPECTED="${2:?Użycie: restore_from_r2.sh PUNKT SUMY.json}"
case "$POINT" in goatcash-restore-test-[0-9]*) ;; *) echo "Niepoprawny punkt: $POINT" >&2; exit 2 ;; esac
for v in PGBACKREST_REPO1_S3_ENDPOINT PGBACKREST_REPO1_S3_KEY PGBACKREST_REPO1_S3_KEY_SECRET PGBACKREST_REPO1_CIPHER_PASS; do
  [ -n "${!v:-}" ] || { echo "Brak zmiennej $v" >&2; exit 2; }
done
# Ten sam obraz (digest) co na serwerze: jedno źródło, compose.yaml.
COMPOSE=infra/compose/staging/compose.yaml
IMAGE="$(sed -n 's/^ *image: *\(timescale\/timescaledb-ha:[^ ]*\).*/\1/p' "$COMPOSE" | head -1)"
case "$IMAGE" in *@sha256:*) ;; *) echo "Brak obrazu Postgres z digestem w $COMPOSE" >&2; exit 1 ;; esac
CONF="$PWD/infra/compose/staging/postgres/pgbackrest.conf"
ID="goatcash-restore-$$"
PW="restore-test-$$-$RANDOM"
start="$(date +%s)"
cleanup() { docker rm -f "$ID" >/dev/null 2>&1 || true; docker volume rm "$ID" >/dev/null 2>&1 || true; }
trap cleanup EXIT
PGBR=(-e PGBACKREST_CONFIG=/etc/pgbackrest/pgbackrest.conf -e PGBACKREST_REPO1_S3_ENDPOINT
      -e PGBACKREST_REPO1_S3_KEY -e PGBACKREST_REPO1_S3_KEY_SECRET -e PGBACKREST_REPO1_CIPHER_PASS
      -v "$CONF:/etc/pgbackrest/pgbackrest.conf:ro")

echo "== odtworzenie z R2 do punktu $POINT (obraz $IMAGE)"
docker volume create "$ID" >/dev/null
docker run --rm -u 0 -v "$ID:/home/postgres/pgdata" --entrypoint chown "$IMAGE" 1000:1000 /home/postgres/pgdata
out="$(docker run --rm "${PGBR[@]}" -v "$ID:/home/postgres/pgdata" --entrypoint pgbackrest "$IMAGE" \
  --stanza=goatcash restore --type=name --target="$POINT" --target-action=promote 2>&1)" ||
  { printf '%s\n' "$out" | tail -20 >&2; echo "FAIL pgbackrest restore" >&2; exit 1; }
echo "  PASS pgbackrest restore (punkt $POINT)"

port=55432
docker run -d --name "$ID" -e POSTGRES_PASSWORD="$PW" -p "127.0.0.1:$port:5432" \
  -v "$ID:/home/postgres/pgdata" "$IMAGE" postgres -c archive_mode=off >/dev/null
ready=0
for _ in $(seq 1 150); do
  r1="$(docker exec "$ID" psql -U postgres -tAc "SELECT NOT pg_is_in_recovery()" 2>/dev/null || true)"
  if [ "$r1" = t ]; then sleep 2
    r2="$(docker exec "$ID" psql -U postgres -tAc "SELECT NOT pg_is_in_recovery()" 2>/dev/null || true)"
    if [ "$r2" = t ]; then ready=1; break; fi
  fi
  sleep 2
done
[ "$ready" = 1 ] || { docker logs "$ID" 2>&1 | tail -30 >&2; echo "FAIL odtworzona instancja nie wstała" >&2; exit 1; }
# Hasło tylko dla tej tymczasowej instancji (pg_authid nie jest tabelą użytkownika w sumach).
docker exec "$ID" psql -U postgres -qc "ALTER USER postgres PASSWORD '$PW'" >/dev/null

restored="$(mktemp)"
uv run --frozen python scripts/pg_checksums.py "postgresql://postgres:$PW@127.0.0.1:$port/postgres" > "$restored"
uv run --frozen python scripts/pg_checksums.py --compare "$EXPECTED" "$restored"
echo "== restore-test: PASS, $(( $(date +%s) - start )) s (odtworzenie + porównanie sum)"
