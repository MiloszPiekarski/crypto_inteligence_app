#!/usr/bin/env bash
# ensure-api-role.sh TAG: konto logowania procesu api (E6, decyzja właściciela 28.11.2026).
# api jest wystawione do internetu, więc nie łączy się kontem postgres z SET ROLE (RESET ROLE
# przywróciłby superużytkownika), tylko kontem goatcash_api: LOGIN, bez członkostw w innych
# rolach, SELECT wyłącznie na tabelach rynkowych, które czyta API (assets, instruments,
# candles_ref, dq_status; recenzja E6: goatcash_readonly widzi też tabele z user_id), bez
# atrybutów uprzywilejowanych, sesja tylko do odczytu, limit połączeń. Po migracjach (tabele
# muszą istnieć; migracja tworząca tabelę od nowa zgubiłaby uprawnienie, więc są nadawane
# przy każdym wdrożeniu). Idempotentne; na końcu asercja: członkostwo, atrybut
# uprzywilejowany albo uprawnienie do innej tabeli = błąd i wdrożenie się przerywa.
#
# Hasło z ./env/api-read.env (PGPASSWORD; tworzy je deploy.sh na serwerze), nie z repo.
# Plik jest czytany bez wykonywania (sed, nie `.`). Hasło idzie do psql przez stdin
# (`\set`), nie w argumentach procesu (widocznych w `ps` na hoście), a sesja wyłącza
# zapis tekstu poleceń w logu serwera przy błędzie i w pg_stat_statements (recenzja E6).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
TAG="${1:?Użycie: ensure-api-role.sh sha-<commit>}"
PASS="$(sed -n 's/^PGPASSWORD=//p' ./env/api-read.env | head -n 1)"
case "$PASS" in
  "" | *[!0-9a-f]*) echo "env/api-read.env: PGPASSWORD musi być niepusty i mieć tylko [0-9a-f]"; exit 1 ;;
esac
{
  printf '\\set pass %s\n' "$PASS"
  cat <<'SQL'
SET client_min_messages = warning;
SET log_min_error_statement = panic;
SET log_statement = none;
SET pg_stat_statements.track_utility = off;
SELECT 'CREATE ROLE goatcash_api LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'goatcash_api') \gexec
SELECT format('ALTER ROLE goatcash_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
              'NOREPLICATION NOBYPASSRLS INHERIT CONNECTION LIMIT 20 PASSWORD %L', :'pass') \gexec
ALTER ROLE goatcash_api SET default_transaction_read_only = on;
ALTER ROLE goatcash_api SET statement_timeout = '5s';
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM goatcash_api;
GRANT SELECT ON assets, instruments, candles_ref, dq_status TO goatcash_api;
SELECT format('REVOKE %I FROM goatcash_api GRANTED BY %I', r.rolname, g.rolname)
FROM pg_auth_members m
JOIN pg_roles r ON r.oid = m.roleid
JOIN pg_roles u ON u.oid = m.member
JOIN pg_roles g ON g.oid = m.grantor
WHERE u.rolname = 'goatcash_api' \gexec
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM pg_roles r
        WHERE pg_has_role('goatcash_api', r.oid, 'MEMBER') AND r.rolname <> 'goatcash_api'
    ) OR EXISTS (
        SELECT FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('public', 'bot') AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND c.relname NOT IN ('assets', 'instruments', 'candles_ref', 'dq_status')
          AND has_table_privilege('goatcash_api', c.oid, 'SELECT, INSERT, UPDATE, DELETE')
    ) OR (
        SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls
        FROM pg_roles WHERE rolname = 'goatcash_api'
    ) THEN
        RAISE EXCEPTION 'goatcash_api: nadmiarowe uprawnienia (członkostwo albo atrybut)';
    END IF;
END $$;
SQL
} | GOATCASH_IMAGE_TAG="$TAG" docker compose exec -T postgres \
  psql -q -v ON_ERROR_STOP=1 -U postgres -d postgres
echo "konto goatcash_api: gotowe (SELECT tylko na tabelach rynkowych, sesja tylko do odczytu)"
