#!/usr/bin/env bash
# scripts/lib/common.sh: wspólne funkcje skryptów (doctor, sondy bramek).
# Muszą działać na macOS właściciela (/bin/bash 3.2, narzędzia BSD) i na Linuksie (CI).
# Testy: gates/probes/shell-portability.sh (bramka G1, w CI także na macOS).

# version_ge CURRENT MIN -> prawda, gdy CURRENT >= MIN (sort -V działa w BSD i GNU sort)
version_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }

# first_version: pierwszy numer wersji (np. 2.40 albo 3.12.1) ze standardowego wejścia
first_version() { grep -Eo '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1; }

# file_mode PLIK -> uprawnienia ósemkowo, np. 600 (stat różni się między macOS a Linuksem)
file_mode() {
  if [ "$(uname -s)" = "Darwin" ]; then stat -f '%Lp' "$1"; else stat -c '%a' "$1"; fi
}
