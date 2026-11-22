#!/usr/bin/env bash
# Sonda G1: gitleaks musi wykryć fałszywy klucz w formacie AWS.
# Klucz jest składany w locie, żeby nie leżał w repozytorium.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
dir="$(mktemp -d)"
trap 'rm -rf "$dir"' EXIT
key="AKIA$(LC_ALL=C tr -dc 'A-Z2-7' </dev/urandom | head -c 16)"
printf 'aws_access_key_id = "%s"\n' "$key" > "$dir/leak.txt"
out="$(gitleaks dir --config .gitleaks.toml --no-banner --redact \
  --report-format json --report-path "$dir/report.json" "$dir/leak.txt" 2>&1)"
if ! grep -q '"RuleID": "aws-access-token"' "$dir/report.json" 2>/dev/null; then
  echo "gitleaks NIE wykrył fałszywego klucza AWS:"; echo "$out" | tail -20; exit 1
fi
echo "gitleaks wykrył fałszywy klucz AWS (reguła aws-access-token)"

# Pliki z sekretami SOPS też są skanowane: fałszywy klucz jako NAZWA klucza w pliku
# o budowie z `sops -e` (SOPS nie szyfruje nazw kluczy) musi zostać wykryty.
probe="infra/secrets/_gate_probe.enc.yaml"
trap 'rm -rf "$dir" "$probe"' EXIT
{ printf '%s: ""\n' "$key"; cat scripts/tests/fixtures/sops_real.yaml; } > "$probe"
if gitleaks dir --config .gitleaks.toml --no-banner --redact "$probe" >/dev/null 2>&1; then
  echo "gitleaks NIE wykrył klucza w $probe (pliki SOPS wyłączone ze skanu?)"; exit 1
fi
echo "gitleaks wykrył klucz w nazwie klucza pliku $probe"
