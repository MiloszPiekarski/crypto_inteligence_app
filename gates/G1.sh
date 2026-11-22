#!/usr/bin/env bash
# Bramka G1 (E1): testy automatyczne z tabeli E1. Testy wymagające GitHuba
# (push protection, ochrona gałęzi, czas CI) są opisane w docs/gates/G1.md.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
PASS=0; FAIL=0
ok()  { printf '  PASS %s\n' "$1"; PASS=$((PASS+1)); }
bad() { printf '  FAIL %s\n' "$1"; FAIL=$((FAIL+1)); }
run() { local name="$1"; shift; if "$@" >/tmp/g1_step.log 2>&1; then ok "$name"; else bad "$name"; tail -20 /tmp/g1_step.log; fi; }

echo "== Jakość kodu =="
run "lint (ruff + Biome)"            make -s lint
run "typy (pyright strict + tsc)"    make -s typecheck
run "granice modułów (import-linter)" make -s imports
run "testy jednostkowe + pokrycie"   make -s test

echo "== Granice modułów: zakazany import musi zostać wykryty =="
bad_file="services/platform/src/goatcash/agents/_impl/_g1_forbidden_probe.py"
echo 'from goatcash.ledger._impl import __doc__ as _probe  # noqa: F401' > "$bad_file"
if uv run lint-imports >/dev/null 2>&1; then bad "import-linter NIE wykrył zakazanego importu"; else ok "import-linter wykrył zakazany import"; fi
rm -f "$bad_file"

echo "== Sekrety: gitleaks =="
run "gitleaks: historia repozytorium czysta" gitleaks git --config .gitleaks.toml --redact --no-banner .
probe_dir="$(mktemp -d)"
# Fałszywy klucz w formacie AWS składany w locie, żeby nie leżał w repozytorium.
fake_key="AKIA$(LC_ALL=C tr -dc 'A-Z2-7' </dev/urandom | head -c 16)"
printf 'aws_access_key_id = "%s"\n' "$fake_key" > "$probe_dir/leak.txt"
if gitleaks dir --config .gitleaks.toml --no-banner "$probe_dir" >/dev/null 2>&1; then
  bad "gitleaks NIE wykrył fałszywego klucza AWS"
else
  ok "gitleaks wykrył fałszywy klucz AWS"
fi
rm -rf "$probe_dir"

echo "== SOPS: odszyfrowanie tylko właściwym kluczem =="
# macOS: SOPS domyślnie szuka klucza w ~/Library/Application Support/sops/age/keys.txt.
# Projekt trzyma klucz local w ~/.config/sops/age/keys.txt (jak na Linuksie),
# więc wskazujemy go jawnie, jeśli zmienna nie jest ustawiona.
if [ -z "${SOPS_AGE_KEY_FILE:-}" ] && [ -f "$HOME/.config/sops/age/keys.txt" ]; then
  export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
fi
if sops -d infra/secrets/local.enc.yaml >/dev/null 2>&1; then ok "klucz local odszyfrowuje local.enc.yaml"
else bad "klucz local NIE odszyfrowuje local.enc.yaml (czy ~/.config/sops/age/keys.txt istnieje?)"; fi
wrong_key="$(mktemp)"; age-keygen -o "$wrong_key" >/dev/null 2>&1
if SOPS_AGE_KEY_FILE="$wrong_key" sops -d infra/secrets/local.enc.yaml >/dev/null 2>&1; then bad "obcy klucz odszyfrował plik"
else ok "obcy klucz odrzucony"; fi
rm -f "$wrong_key"

printf '\n== G1 (automatyczne): %d PASS, %d FAIL ==\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
