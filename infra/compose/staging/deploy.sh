#!/usr/bin/env bash
# deploy.sh TAG: wdrożenie staging na serwerze (roadmapa E3, zakres 7; ADR-0007 pkt 5).
# Uruchamia go deploy-staging.yml przez SSH (Tailscale) w /srv/goatcash/compose.
#   1. zapamiętuje bieżący tag obrazu (do rollbacku);
#   2. pobiera nowe obrazy; pusty wolumen bazy + kopia w repozytorium = odtworzenie z kopii;
#      uruchamia bazę i Valkey, zakłada stanzę pgBackRest (idempotentnie);
#   3. uruchamia migracje z nowego obrazu (alembic upgrade head, kontener ingest z api.env)
#      i zakłada konto api tylko do odczytu (ensure-api-role.sh, po migracjach);
#   4. podnosi całość i czeka na healthchecki;
#   5. test dymny: /v1/health przez Caddy (TLS, nagłówek Host jak z Cloudflare);
#   6. przy błędzie w krokach 4-5: powrót do poprzedniego tagu i kod błędu 1.
# Migracje muszą być wstecznie zgodne (expand/contract): rollback cofa obraz, nie schemat.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
TAG="${1:?Użycie: deploy.sh sha-<commit>}"
case "$TAG" in sha-[0-9a-f]*) ;; *) echo "Niepoprawny tag obrazu: $TAG"; exit 2 ;; esac
PREV="$(cat .image-tag 2>/dev/null || true)"
PORT="${GOATCASH_HTTPS_PORT:-443}"

compose() { GOATCASH_IMAGE_TAG="$1" docker compose "${@:2}"; }

smoke() {
  local i body
  for i in $(seq 1 30); do
    body="$(curl -fsS --max-time 5 -k --resolve "api.goatcash.app:${PORT}:127.0.0.1" \
      "https://api.goatcash.app:${PORT}/v1/health" 2>/dev/null || true)"
    if grep -q '"status":"ok"' <<<"$body"; then
      echo "test dymny: OK (próba $i)"
      return 0
    fi
    sleep 2
  done
  echo "test dymny: BŁĄD (/v1/health nie odpowiada ok)"
  return 1
}

rollback() {
  if [ -z "$PREV" ]; then
    echo "ROLLBACK: brak poprzedniego tagu (pierwsze wdrożenie); zostawiam stan do diagnozy"
    return 1
  fi
  echo "ROLLBACK do $PREV"
  compose "$PREV" up -d --wait --remove-orphans
  smoke
}

# Nowy serwer (odtworzenie od zera, F-01): pusty wolumen bazy, a w repozytorium kopii jest
# stanza z kopiami. Wtedy najpierw odtwarzamy bazę z kopii (najnowsza kopia + cały WAL),
# zamiast zakładać pustą bazę (stanza-create i tak odrzuciłby obcą instancję).
restore_if_empty() {
  local pg=(compose "$1" run --rm --no-deps -T --entrypoint)
  if "${pg[@]}" test postgres -s /home/postgres/pgdata/data/PG_VERSION; then return 0; fi
  local info
  info="$("${pg[@]}" pgbackrest postgres --stanza=goatcash --output=json info 2>/dev/null || true)"
  if grep -q '"backup":\[{' <<<"$info"; then
    echo "== pusty wolumen bazy, kopia w repozytorium: odtwarzam z kopii"
    "${pg[@]}" pgbackrest postgres --stanza=goatcash restore
    echo "odtworzenie z kopii: OK"
  else
    echo "== pusty wolumen bazy i brak kopii: nowa baza"
  fi
}

# Po odtworzeniu z kopii Postgres jest „zdrowy”, ale jeszcze odgrywa WAL (tryb recovery);
# stanza-create i migracje wymagają serwera głównego (wdrożenie 45509198812: „are all
# available clusters in recovery?”). Czekamy na koniec odtwarzania, najwyżej 15 min.
wait_primary() {
  local i r
  for i in $(seq 1 180); do
    r="$(compose "$1" exec -T postgres psql -U postgres -tAc "SELECT pg_is_in_recovery()" 2>/dev/null || true)"
    if [ "$r" = f ]; then
      [ "$i" -eq 1 ] || echo "baza poza trybem odtwarzania (po ${i}. próbie)"
      return 0
    fi
    sleep 5
  done
  echo "baza nadal w trybie odtwarzania po 15 min"
  return 1
}

echo "== wdrożenie $TAG (poprzedni: ${PREV:-brak})"
# GOATCASH_SKIP_PULL=1 tylko w teście (obraz zbudowany lokalnie, nie w GHCR).
[ "${GOATCASH_SKIP_PULL:-0}" = 1 ] || compose "$TAG" pull --quiet
restore_if_empty "$TAG"
compose "$TAG" up -d --wait postgres valkey
wait_primary "$TAG"
compose "$TAG" exec -T postgres pgbackrest --stanza=goatcash stanza-create
compose "$TAG" exec -T postgres pgbackrest --stanza=goatcash check
./ensure-roles.sh "$TAG"
# Migracje kontenerem ingest (api.env, konto postgres); api ma tylko konto do odczytu (E6).
compose "$TAG" run --rm --no-deps -T ingest alembic upgrade head
./ensure-api-role.sh "$TAG"

if compose "$TAG" up -d --wait --remove-orphans && smoke; then
  echo "$TAG" > .image-tag
  echo "== wdrożono $TAG"
else
  echo "== wdrożenie $TAG nieudane"
  rollback || true
  exit 1
fi
