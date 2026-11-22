#!/usr/bin/env bash
# Sonda G1: funkcje z scripts/lib/common.sh dają poprawne wyniki w danym środowisku.
# W CI uruchamiana także na macOS z systemowym /bin/bash 3.2 i BSD sort (środowisko właściciela).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
# shellcheck source=scripts/lib/common.sh
. scripts/lib/common.sh
fail=0
check() { if "$@"; then echo "ok: $*"; else echo "BŁĄD: $*"; fail=1; fi; }
nope()  { if "$@"; then echo "BŁĄD (powinno być fałszem): $*"; fail=1; else echo "ok: nie $*"; fi; }
echo "bash ${BASH_VERSION}, sort: $(command -v sort), system: $(uname -s)"
check version_ge 1.10 1.9
check version_ge 2.40 2.40
check version_ge 3.12.1 3.12
nope  version_ge 2.39 2.40
nope  version_ge 1.9 1.10
ver="$(printf 'git version 2.47.1 (Apple Git-154)\n' | first_version)"
check [ "$ver" = "2.47.1" ]
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
chmod 600 "$tmp"
check [ "$(file_mode "$tmp")" = "600" ]
exit "$fail"
