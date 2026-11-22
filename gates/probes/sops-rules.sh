#!/usr/bin/env bash
# Sonda G1: reguły infra/secrets/.sops.yaml przypisują każdemu środowisku
# dokładnie jeden, własny klucz age, a local.enc.yaml jest zaszyfrowany
# wyłącznie kluczem local. Nie wymaga kluczy prywatnych (działa też w CI).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
cfg="infra/secrets/.sops.yaml"
dir="$(mktemp -d)"
trap 'rm -rf "$dir"' EXIT
# Bez tablic asocjacyjnych: /bin/bash na macOS to wersja 3.2.
recipients() { grep -E '^[[:space:]]+recipient:' "$1" | awk '{print $2}' | sort -u; }
for env in local staging production; do
  printf 'probe: "1"\n' > "$dir/$env.enc.yaml"
  if ! sops --config "$cfg" -e -i "$dir/$env.enc.yaml" 2>"$dir/err"; then
    echo "sops nie zaszyfrował pliku $env.enc.yaml według reguł:"; cat "$dir/err"; exit 1
  fi
  r="$(recipients "$dir/$env.enc.yaml")"
  if [ "$(wc -l <<<"$r")" -ne 1 ] || [ -z "$r" ]; then
    echo "$env: oczekiwano dokładnie jednego odbiorcy, jest: $r"; exit 1
  fi
  eval "got_$env=\"\$r\""
  echo "$env -> $r"
done
if [ "$got_local" = "$got_staging" ] || [ "$got_local" = "$got_production" ] \
  || [ "$got_staging" = "$got_production" ]; then
  echo "BŁĄD: dwa środowiska mają ten sam klucz"; exit 1
fi
real="$(recipients infra/secrets/local.enc.yaml)"
if [ "$real" != "$got_local" ]; then
  echo "BŁĄD: local.enc.yaml ma odbiorców '$real', oczekiwano '$got_local'"; exit 1
fi
echo "każde środowisko ma własny klucz; local.enc.yaml zaszyfrowany tylko kluczem local"
