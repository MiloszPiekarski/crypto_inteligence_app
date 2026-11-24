#!/usr/bin/env bash
# backup.sh full|incr: kopia pgBackRest do R2 (roadmapa E3, zakres 5). Uruchamia systemd timer
# (Ansible): pełna w niedzielę, przyrostowa w pozostałe dni. Po sukcesie zapisuje metrykę
# goatcash_backup_last_success_timestamp_seconds (node-exporter, katalog textfile); alert
# „brak kopii > 26 h” (Grafana) liczy wiek tej metryki.
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
echo "kopia $TYPE: OK"
