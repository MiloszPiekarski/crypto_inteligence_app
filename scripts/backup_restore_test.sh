#!/usr/bin/env bash
# make backup-restore-test (bramka G3 `backup-restore`, F-02): pgBackRest na prawdziwym obrazie
# bazy (ten sam digest co Compose staging), z tą samą konfiguracją co staging, ale z lokalnym
# repozytorium (posix) zamiast R2. Sprawdza:
#   1. kopię pełną + przyrostową + ciągłe archiwum WAL, szyfrowanie AES-256;
#   2. odtworzenie najnowszego stanu do CZYSTEJ instancji: 100% tabel zgodnych (liczba + MD5);
#   3. odtworzenie do punktu w czasie (PITR): stan sprzed ostatnich zapisów, 100% tabel zgodnych.
# Schemat bazy: prawdziwe migracje (alembic upgrade head) + tabela testowa jako hypertable.
# Kopie na R2 sprawdza co tydzień workflow restore-test.yml (dowód G3 `restore-test`).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
IMAGE="timescale/timescaledb-ha:pg17@sha256:c72b4cb8aaa0a52c0870c2b0a48173c595ee9bef0f3d8f92c3f546c69fef3567"
CONF="$PWD/infra/compose/staging/postgres/pgbackrest.conf"
ID="g3br$$"
PW="test-$(date +%s)"
CIPHER="cipher-$$"
WORK="$(mktemp -d)"
cleanup() {
  docker rm -f "$ID-pg1" "$ID-pg2" "$ID-pg3" >/dev/null 2>&1 || true
  docker volume rm "$ID-repo" "$ID-pg1" "$ID-pg2" "$ID-pg3" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT
fail() { echo "  FAIL $*" >&2; exit 1; }
ok() { echo "  PASS $*"; }

# Zmienne pgBackRest: repozytorium lokalne zamiast R2 (nadpisuje repo1-type z pliku).
PGBR=(-e PGBACKREST_CONFIG=/etc/pgbackrest/pgbackrest.conf -e PGBACKREST_REPO1_TYPE=posix -e PGBACKREST_REPO1_PATH=/repo
      -e PGBACKREST_REPO1_CIPHER_PASS="$CIPHER" -e POSTGRES_PASSWORD="$PW")
ARCHIVE=(postgres -c wal_level=replica -c archive_mode=on
         -c "archive_command=pgbackrest --stanza=goatcash archive-push %p" -c archive_timeout=60)

docker volume create "$ID-repo" >/dev/null
docker run --rm -u 0 -v "$ID-repo:/repo" --entrypoint chown "$IMAGE" 1000:1000 /repo

start_pg() { # nazwa wolumen port [dodatkowe argumenty postgres]
  local name="$1" vol="$2" port="$3"; shift 3
  docker run -d --name "$ID-$name" "${PGBR[@]}" -p "127.0.0.1:$port:5432" \
    -v "$vol:/home/postgres/pgdata" -v "$ID-repo:/repo" -v "$CONF:/etc/pgbackrest/pgbackrest.conf:ro" \
    "$IMAGE" "${ARCHIVE[@]}" "$@" >/dev/null
}
wait_ready() { # nazwa
  for _ in $(seq 1 90); do
    # Po starcie entrypoint obrazu może jeszcze restartować serwer: wymagamy 2 udanych odczytów.
    if docker exec "$ID-$1" psql -U postgres -tAc "SELECT NOT pg_is_in_recovery()" 2>/dev/null | grep -q t &&
      sleep 2 && docker exec "$ID-$1" psql -U postgres -tAc "SELECT NOT pg_is_in_recovery()" 2>/dev/null | grep -q t; then return 0; fi
    sleep 2
  done
  docker logs "$ID-$1" | tail -30
  fail "instancja $1 nie wystartowała"
}
psql_pg1() { docker exec -i "$ID-pg1" psql -v ON_ERROR_STOP=1 -U postgres -d postgres "$@"; }
pgbr() { # nazwa polecenie...: wynik pokazywany tylko przy błędzie
  local out
  out="$(docker exec "$ID-$1" pgbackrest --stanza=goatcash "${@:2}" 2>&1)" || { printf '%s\n' "$out" | tail -20 >&2; fail "pgbackrest ${*:2}"; }
  printf '%s\n' "$out"
}
dsn() { echo "postgresql://postgres:$PW@127.0.0.1:$1/postgres"; }
free_port() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])'; }

echo "== instancja źródłowa, migracje, dane"
P1="$(free_port)"
docker volume create "$ID-pg1" >/dev/null
start_pg pg1 "$ID-pg1" "$P1"
wait_ready pg1
pgbr pg1 stanza-create >/dev/null
GOATCASH_DATABASE_URL="postgresql+psycopg://postgres:$PW@127.0.0.1:$P1/postgres" \
  uv run --frozen alembic -c services/platform/alembic.ini upgrade head >/dev/null
psql_pg1 -q <<'SQL'
CREATE TABLE IF NOT EXISTS public.f02_probe (ts timestamptz NOT NULL, batch text NOT NULL, v bigint NOT NULL);
SELECT 1 FROM create_hypertable('public.f02_probe', 'ts', if_not_exists => TRUE) \g /dev/null
INSERT INTO public.f02_probe SELECT now() - make_interval(mins => g), 'A', g FROM generate_series(1, 5000) g;
INSERT INTO public.assets (symbol, name) VALUES ('F02A', 'probe A');
SQL
ok "migracje alembic + dane A ($(psql_pg1 -tAc 'SELECT count(*) FROM f02_probe') wierszy w hypertable)"

pgbr pg1 --type=full backup >/dev/null
INFO="$(pgbr pg1 info --output=json)"
FULL_SET="$(printf '%s' "$INFO" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["backup"][-1]["label"])')"
ok "kopia pełna $FULL_SET (szyfrowana: $(printf '%s' "$INFO" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["cipher"])'))"

psql_pg1 -q -c "INSERT INTO public.f02_probe SELECT now(), 'B', g FROM generate_series(1, 3000) g;"
psql_pg1 -q -c "SELECT pg_switch_wal();" >/dev/null
uv run --frozen python scripts/pg_checksums.py "$(dsn "$P1")" > "$WORK/at_target.json"
TARGET="$(psql_pg1 -tAc "SELECT to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.US') || '+00'")"
sleep 2
psql_pg1 -q -c "INSERT INTO public.f02_probe SELECT now(), 'C', g FROM generate_series(1, 2000) g; DELETE FROM public.assets WHERE symbol = 'F02A';"
pgbr pg1 --type=incr backup >/dev/null
ok "kopia przyrostowa po zmianach C"
psql_pg1 -q -c "SELECT pg_switch_wal();" >/dev/null
uv run --frozen python scripts/pg_checksums.py "$(dsn "$P1")" > "$WORK/latest.json"
pgbr pg1 check >/dev/null
ok "archiwum WAL kompletne (pgbackrest check)"
docker stop "$ID-pg1" >/dev/null

restore_into() { # nazwa port [opcje restore]
  local name="$1" port="$2"; shift 2
  docker volume create "$ID-$name" >/dev/null
  local out
  out="$(docker run --rm "${PGBR[@]}" -v "$ID-$name:/home/postgres/pgdata" -v "$ID-repo:/repo" \
    -v "$CONF:/etc/pgbackrest/pgbackrest.conf:ro" --entrypoint pgbackrest "$IMAGE" \
    --stanza=goatcash --delta restore "$@" 2>&1)" || { printf '%s\n' "$out" | tail -20 >&2; fail "pgbackrest restore $*"; }
  start_pg "$name" "$ID-$name" "$port"
  wait_ready "$name"
}

echo "== odtworzenie najnowszego stanu do czystej instancji"
P2="$(free_port)"
restore_into pg2 "$P2"
uv run --frozen python scripts/pg_checksums.py "$(dsn "$P2")" > "$WORK/restored.json"
uv run --frozen python scripts/pg_checksums.py --compare "$WORK/latest.json" "$WORK/restored.json" \
  || fail "odtworzony stan różni się od źródła"
ok "odtworzenie najnowszego stanu: wszystkie tabele zgodne"

echo "== odtworzenie do punktu w czasie ($TARGET)"
P3="$(free_port)"
# Kopia bazowa wskazana jawnie (pełna sprzed punktu docelowego) + WAL do punktu w czasie.
restore_into pg3 "$P3" --set="$FULL_SET" --type=time --target="$TARGET" --target-action=promote
uv run --frozen python scripts/pg_checksums.py "$(dsn "$P3")" > "$WORK/pitr.json"
uv run --frozen python scripts/pg_checksums.py --compare "$WORK/at_target.json" "$WORK/pitr.json" \
  || fail "stan po PITR różni się od stanu w punkcie docelowym"
if uv run --frozen python scripts/pg_checksums.py --compare "$WORK/latest.json" "$WORK/pitr.json" >/dev/null; then
  fail "PITR dał stan najnowszy zamiast stanu z punktu docelowego"
fi
ok "PITR: stan z punktu w czasie, bez zmian C; wszystkie tabele zgodne"
echo "backup-restore-test: OK"
