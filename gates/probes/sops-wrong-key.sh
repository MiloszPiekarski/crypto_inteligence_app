#!/usr/bin/env bash
# Sonda G1: obcy klucz age (świeżo wygenerowany) NIE odszyfrowuje local.enc.yaml.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
key="$(mktemp)"
trap 'rm -f "$key"' EXIT
rm -f "$key"
age-keygen -o "$key" 2>/dev/null || { echo "age-keygen nie działa"; exit 1; }
if SOPS_AGE_KEY_FILE="$key" sops -d infra/secrets/local.enc.yaml >/dev/null 2>&1; then
  echo "BŁĄD: obcy klucz odszyfrował local.enc.yaml"
  exit 1
fi
echo "obcy klucz odrzucony"
