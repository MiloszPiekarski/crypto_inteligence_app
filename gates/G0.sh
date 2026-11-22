#!/usr/bin/env bash
# Bramka G0 (E0): gotowość komputera i dostęp do usług. Część ręczna (2FA kont)
# jest opisana w docs/gates/G0.md.
set -uo pipefail
exec "$(dirname "${BASH_SOURCE[0]}")/../scripts/doctor.sh"
