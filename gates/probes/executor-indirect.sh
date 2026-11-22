#!/usr/bin/env bash
# Sonda G1: executor nie może dostać modułu domenowego pośrednio. Na czas sondy
# common.api (którego executor używa) importuje marketdata.api; import-linter
# musi złamać kontrakt executora. Plik jest przywracany z kopii (trap EXIT).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
target="services/platform/src/goatcash/common/api.py"
backup="$(mktemp)"
cp "$target" "$backup"
trap 'cp "$backup" "$target"; rm -f "$backup"' EXIT
printf '\nimport goatcash.marketdata.api as _gate_probe  # sonda G1\n' >> "$target"
out="$(uv run --frozen lint-imports 2>&1)"
if grep -q "executor: tylko bot_core.api i common.api BROKEN" <<<"$out"; then
  echo "import-linter wykrył pośredni import modułu domenowego w executorze"
  exit 0
fi
echo "import-linter NIE wykrył pośredniego importu w executorze:"
echo "$out" | tail -20
exit 1
