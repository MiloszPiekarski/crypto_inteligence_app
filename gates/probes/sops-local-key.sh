#!/usr/bin/env bash
# Sonda G1: prawdziwy klucz prywatny local odszyfrowuje infra/secrets/local.enc.yaml.
# macOS: SOPS domyślnie szuka klucza w ~/Library/Application Support/sops/age/keys.txt,
# a projekt trzyma go w ~/.config/sops/age/keys.txt, więc wskazujemy go jawnie.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
if [ -z "${SOPS_AGE_KEY_FILE:-}" ] && [ -f "$HOME/.config/sops/age/keys.txt" ]; then
  export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
fi
if sops -d infra/secrets/local.enc.yaml >/dev/null; then
  echo "klucz local odszyfrowuje local.enc.yaml"
  exit 0
fi
echo "klucz local NIE odszyfrowuje local.enc.yaml (czy ~/.config/sops/age/keys.txt istnieje?)"
exit 1
