#!/usr/bin/env bash
# Sonda G1: reguły infra/secrets/.sops.yaml przypisują każdemu środowisku
# dokładnie jeden, własny klucz age, a local.enc.yaml jest zaszyfrowany
# wyłącznie kluczem local. Nie wymaga kluczy prywatnych (działa też w CI).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
cfg="infra/secrets/.sops.yaml"
dir="$(mktemp -d)"
trap 'rm -rf "$dir"' EXIT
recipients() { grep -E '^[[:space:]]+recipient:' "$1" | awk '{print $2}' | sort -u; }

# recipient_for ŚRODOWISKO -> jedyny odbiorca pliku tego środowiska według reguł
recipient_for() {
  local env="$1" file r
  file="$dir/$1.enc.yaml"
  printf 'probe: "1"\n' > "$file"
  if ! sops --config "$cfg" -e -i "$file" 2>"$dir/err"; then
    echo "sops nie zaszyfrował pliku $env.enc.yaml według reguł:" >&2; cat "$dir/err" >&2; return 1
  fi
  r="$(recipients "$file")"
  if [ -z "$r" ] || [ "$(printf '%s\n' "$r" | wc -l | tr -d ' ')" -ne 1 ]; then
    echo "$env: oczekiwano dokładnie jednego odbiorcy, jest: '$r'" >&2; return 1
  fi
  printf '%s' "$r"
}

r_local="$(recipient_for local)" || exit 1
r_staging="$(recipient_for staging)" || exit 1
r_production="$(recipient_for production)" || exit 1
echo "local -> $r_local"
echo "staging -> $r_staging"
echo "production -> $r_production"
if [ "$r_local" = "$r_staging" ] || [ "$r_local" = "$r_production" ] || [ "$r_staging" = "$r_production" ]; then
  echo "BŁĄD: dwa środowiska mają ten sam klucz"; exit 1
fi
real="$(recipients infra/secrets/local.enc.yaml)"
if [ "$real" != "$r_local" ]; then
  echo "BŁĄD: local.enc.yaml ma odbiorców '$real', oczekiwano '$r_local'"; exit 1
fi
echo "każde środowisko ma własny klucz; local.enc.yaml zaszyfrowany tylko kluczem local"
