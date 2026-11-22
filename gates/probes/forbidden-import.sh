#!/usr/bin/env bash
# Sonda G1: celowo zakazany import (agents._impl -> ledger._impl) musi zostać wykryty.
# Kod wyjścia 0 = import-linter ODRZUCIŁ zakazany import (czyli ochrona działa).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
probe="services/platform/src/goatcash/agents/_impl/_gate_forbidden_probe.py"
trap 'rm -f "$probe"' EXIT
printf 'import goatcash.ledger._impl as ledger_impl\n\nPROBE = ledger_impl.__doc__\n' > "$probe"
out="$(uv run --frozen lint-imports 2>&1)"
if grep -q "goatcash.agents._impl._gate_forbidden_probe -> goatcash.ledger._impl" <<<"$out"; then
  echo "import-linter wykrył zakazany import"
  exit 0
fi
echo "import-linter NIE wykrył zakazanego importu:"
echo "$out" | tail -20
exit 1
