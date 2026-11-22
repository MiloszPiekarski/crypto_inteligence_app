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
if grep -q '"RuleID": "aws-access-token"' "$dir/report.json" 2>/dev/null; then
  echo "gitleaks wykrył fałszywy klucz AWS (reguła aws-access-token)"
  exit 0
fi
echo "gitleaks NIE wykrył fałszywego klucza AWS:"
echo "$out" | tail -20
exit 1
