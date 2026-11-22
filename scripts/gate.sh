#!/usr/bin/env bash
# scripts/gate.sh <nr> – uruchamia testy automatyczne bramki G<nr> (plik gates/G<nr>.sh),
# zapisuje pełny wynik do reports/gates/G<nr>-<czas UTC>.log i zwraca kod wyjścia testów.
# W CI katalog reports/gates/ jest publikowany jako artefakt.
set -euo pipefail
nr="${1:?Użycie: scripts/gate.sh <nr>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
script="${ROOT}/gates/G${nr}.sh"
[ -x "$script" ] || { echo "Brak testów automatycznych dla bramki G${nr} (${script})"; exit 2; }
mkdir -p "${ROOT}/reports/gates"
log="${ROOT}/reports/gates/G${nr}-$(date -u +%Y%m%dT%H%M%SZ).log"
{
  echo "Bramka G${nr} | commit $(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo brak) | $(date -u +%FT%TZ)"
  echo "------------------------------------------------------------"
} > "$log"
set +e
"$script" 2>&1 | tee -a "$log"
rc=${PIPESTATUS[0]}
set -e
if [ "$rc" -eq 0 ]; then echo "WYNIK: G${nr} testy automatyczne ZIELONE" | tee -a "$log"
else echo "WYNIK: G${nr} testy automatyczne CZERWONE (kod $rc)" | tee -a "$log"; fi
echo "Raport: ${log#"$ROOT"/}"
exit "$rc"
