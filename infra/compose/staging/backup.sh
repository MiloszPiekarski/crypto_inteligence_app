#!/usr/bin/env bash
# backup.sh full|incr: kopia pgBackRest do R2 (roadmapa E3, zakres 5). Uruchamia systemd timer
# (Ansible): pełna w niedzielę, przyrostowa w pozostałe dni. Po sukcesie zapisuje metrykę
# goatcash_backup_last_success_timestamp_seconds (node-exporter, katalog textfile); alert
# „brak kopii > 26 h” (Grafana) liczy wiek tej metryki. Retencja (30 dni, pgbackrest.conf):
# pgBackRest usuwa stare kopie przy każdej kopii; goatcash_backup_oldest_timestamp_seconds
# (najstarsza kopia w repozytorium) i alert „Retencja kopii nie dziala” to jej dowód.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
TYPE="${1:?Użycie: backup.sh full|incr}"
case "$TYPE" in full|incr) ;; *) echo "Typ kopii: full albo incr"; exit 2 ;; esac
TAG="$(cat .image-tag)"
METRICS_DIR="${GOATCASH_METRICS_DIR:-../metrics}"

GOATCASH_IMAGE_TAG="$TAG" docker compose exec -T postgres \
  pgbackrest --stanza=goatcash --type="$TYPE" backup

tmp="$(mktemp "$METRICS_DIR/backup.prom.XXXXXX")"
{
  echo "# HELP goatcash_backup_last_success_timestamp_seconds Czas ostatniej udanej kopii pgBackRest."
  echo "# TYPE goatcash_backup_last_success_timestamp_seconds gauge"
  echo "goatcash_backup_last_success_timestamp_seconds{type=\"$TYPE\"} $(date +%s)"
} > "$tmp"
chmod 0644 "$tmp"
mv "$tmp" "$METRICS_DIR/backup-$TYPE.prom"

# Stan repozytorium po kopii (pgBackRest właśnie wykonał expire): najstarsza kopia i liczba
# pełnych. Wynik do zmiennej, bez `cmd | python3`, żeby błąd pgbackrest info nie zginął.
info="$(GOATCASH_IMAGE_TAG="$TAG" docker compose exec -T postgres \
  pgbackrest --stanza=goatcash info --output=json)"
tmp="$(mktemp "$METRICS_DIR/retention.prom.XXXXXX")"
python3 -c '
import json, sys
backups = json.loads(sys.argv[1])[0]["backup"]
if not backups:
    sys.exit("pgbackrest info: brak kopii po udanej kopii")
oldest = min(b["timestamp"]["start"] for b in backups)
full = sum(1 for b in backups if b["type"] == "full")
print("# HELP goatcash_backup_oldest_timestamp_seconds Początek najstarszej kopii w repozytorium pgBackRest.")
print("# TYPE goatcash_backup_oldest_timestamp_seconds gauge")
print(f"goatcash_backup_oldest_timestamp_seconds {oldest}")
print("# HELP goatcash_backup_full_count Liczba pełnych kopii w repozytorium pgBackRest.")
print("# TYPE goatcash_backup_full_count gauge")
print(f"goatcash_backup_full_count {full}")
' "$info" > "$tmp"
chmod 0644 "$tmp"
mv "$tmp" "$METRICS_DIR/backup-retention.prom"
echo "kopia $TYPE: OK"
