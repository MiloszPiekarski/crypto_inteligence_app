#!/usr/bin/env bash
# ensure-roles.sh TAG: rola tylko do odczytu metryk dla postgres-exporter (pg_monitor).
# Idempotentne; hasło z ./env/postgres-exporter.env (DATA_SOURCE_PASS), nie z repo.
# Plik czytany bez wykonywania; hasło idzie do psql przez stdin (`\set`), nie w argumentach
# procesu, a sesja nie zapisuje tekstu poleceń w logu serwera ani w pg_stat_statements
# (recenzja E6, ten sam wzorzec co ensure-api-role.sh).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
TAG="${1:?Użycie: ensure-roles.sh sha-<commit>}"
PASS="$(sed -n 's/^DATA_SOURCE_PASS=//p' ./env/postgres-exporter.env | head -n 1)"
case "$PASS" in
  "" | *[!0-9A-Za-z_-]*) echo "env/postgres-exporter.env: DATA_SOURCE_PASS pusty albo z niedozwolonymi znakami"; exit 1 ;;
esac
{
  printf '\\set pass %s\n' "$PASS"
  cat <<'SQL'
SET client_min_messages = warning;
SET log_min_error_statement = panic;
SET log_statement = none;
SET pg_stat_statements.track_utility = off;
SELECT format('CREATE ROLE goatcash_monitor LOGIN IN ROLE pg_monitor PASSWORD %L', :'pass')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'goatcash_monitor') \gexec
SELECT format('ALTER ROLE goatcash_monitor PASSWORD %L', :'pass') \gexec
SQL
} | GOATCASH_IMAGE_TAG="$TAG" docker compose exec -T postgres \
  psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres
