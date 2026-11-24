#!/usr/bin/env bash
# ensure-roles.sh TAG: rola tylko do odczytu metryk dla postgres-exporter (pg_monitor).
# Idempotentne; hasło z ./env/postgres-exporter.env (DATA_SOURCE_PASS), nie z repo.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
TAG="${1:?Użycie: ensure-roles.sh sha-<commit>}"
# shellcheck disable=SC1091
PASS="$(. ./env/postgres-exporter.env && printf '%s' "$DATA_SOURCE_PASS")"
GOATCASH_IMAGE_TAG="$TAG" docker compose exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U postgres -d postgres -v pass="$PASS" <<'SQL'
SELECT format('CREATE ROLE goatcash_monitor LOGIN IN ROLE pg_monitor PASSWORD %L', :'pass')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'goatcash_monitor') \gexec
SELECT format('ALTER ROLE goatcash_monitor PASSWORD %L', :'pass') \gexec
SQL
