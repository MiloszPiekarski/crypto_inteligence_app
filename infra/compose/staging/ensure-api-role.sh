#!/usr/bin/env bash
# ensure-api-role.sh TAG: konto logowania procesu api (E6, decyzja właściciela 28.11.2026).
# api jest wystawione do internetu, więc nie łączy się kontem postgres z SET ROLE (RESET ROLE
# przywróciłby superużytkownika), tylko kontem goatcash_api: LOGIN, członek wyłącznie
# goatcash_readonly, bez atrybutów uprzywilejowanych, sesja tylko do odczytu, limit połączeń.
# Po migracjach (grupa goatcash_readonly powstaje w migracji 0001). Idempotentne; atrybuty
# i członkostwa ustawiane przy każdym wdrożeniu (ręczna zmiana na serwerze nie przetrwa).
# Hasło z ./env/api-read.env (PGPASSWORD, z SOPS), nie z repo; nie jest wypisywane.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
TAG="${1:?Użycie: ensure-api-role.sh sha-<commit>}"
# shellcheck disable=SC1091
PASS="$(. ./env/api-read.env && printf '%s' "$PGPASSWORD")"
case "$PASS" in
  "" | *[!0-9a-f]*) echo "env/api-read.env: PGPASSWORD musi być niepusty i mieć tylko [0-9a-f]"; exit 1 ;;
esac
GOATCASH_IMAGE_TAG="$TAG" docker compose exec -T postgres \
  psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres -v pass="$PASS" <<'SQL'
SET client_min_messages = warning;
SELECT 'CREATE ROLE goatcash_api LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'goatcash_api') \gexec
SELECT format('ALTER ROLE goatcash_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
              'NOREPLICATION NOBYPASSRLS INHERIT CONNECTION LIMIT 20 PASSWORD %L', :'pass') \gexec
ALTER ROLE goatcash_api SET default_transaction_read_only = on;
ALTER ROLE goatcash_api SET statement_timeout = '5s';
GRANT goatcash_readonly TO goatcash_api;
SELECT format('REVOKE %I FROM goatcash_api', r.rolname)
FROM pg_auth_members m
JOIN pg_roles r ON r.oid = m.roleid
JOIN pg_roles u ON u.oid = m.member
WHERE u.rolname = 'goatcash_api' AND r.rolname <> 'goatcash_readonly' \gexec
SQL
echo "konto goatcash_api: gotowe (tylko goatcash_readonly, sesja tylko do odczytu)"
