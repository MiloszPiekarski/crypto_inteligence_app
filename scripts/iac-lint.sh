#!/usr/bin/env bash
# scripts/iac-lint.sh (make iac-lint, bramka G3 `iac-lint`): statyczna kontrola IaC.
#   Terraform: fmt -check, init -backend=false (lockfile tylko do odczytu), validate, tflint;
#   trivy config (błędne konfiguracje HIGH/CRITICAL, wbudowane reguły, bez pobierania);
#   Ansible: ansible-lint, profil production, offline.
# Dwie części, obie muszą przejść:
#   1. autotest na wzorcach (scripts/tests/fixtures/iac): każde narzędzie przepuszcza poprawny
#      wzorzec i ODRZUCA błędny; narzędzie, które niczego nie odrzuca, niczego nie sprawdza;
#   2. prawdziwe IaC: wymagane katalogi muszą istnieć (puste infra/ to FAIL, nie „zielony
#      lint niczego”) i przejść wszystkie narzędzia.
# Narzędzia w wersjach z CI: `make tools` (.tools/bin) i `uv sync` (ansible-lint w .venv).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
if [ -d .tools/bin ]; then PATH="$PWD/.tools/bin:$PATH"; fi
if [ -d .venv/bin ]; then PATH="$PATH:$PWD/.venv/bin"; fi
fail=0
need() { command -v "$1" >/dev/null || { echo "Brak narzędzia: $1 (uruchom: make tools, uv sync)"; fail=1; }; }
for t in terraform tflint trivy ansible-lint; do need "$t"; done
[ "$fail" -eq 0 ] || exit 1

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
# Dane Terraform i cache trivy poza repozytorium; bez sprawdzania nowszych wersji tflint.
export TF_DATA_DIR="$work/tf" TF_IN_AUTOMATION=1 TFLINT_DISABLE_VERSION_CHECK=1
TFLINT_CONFIG="$PWD/infra/terraform/.tflint.hcl"
FIX=scripts/tests/fixtures/iac

ok() { echo "  PASS $*"; }
bad() { echo "  FAIL $*"; fail=1; }

tf_fmt() { terraform -chdir="$1" fmt -check -recursive -diff -no-color; }
tf_validate() {
  rm -rf "$TF_DATA_DIR"
  terraform -chdir="$1" init -backend=false -input=false -lockfile=readonly -no-color >/dev/null &&
    terraform -chdir="$1" validate -no-color
}
tf_lint() { tflint --chdir="$1" --config="$TFLINT_CONFIG" --no-color; }
trivy_config() {
  trivy config --quiet --cache-dir "$work/trivy" --skip-check-update --exit-code 1 \
    --severity HIGH,CRITICAL "$1"
}
ansible_lint() { ansible-lint --offline --profile production --nocolor "$1"; }

# expect WYNIK OPIS KOMENDA...: WYNIK=pass (musi przejść) albo reject (musi zostać odrzucone).
expect() {
  local want="$1" what="$2"; shift 2
  local out; out="$("$@" 2>&1)"; local rc=$?
  if [ "$want" = pass ] && [ "$rc" -eq 0 ]; then ok "$what"
  elif [ "$want" = reject ] && [ "$rc" -ne 0 ]; then ok "$what (odrzucony, kod $rc)"
  else
    bad "$what (kod $rc, oczekiwano: $want)"
    printf '%s\n' "$out" | tail -20 | sed 's/^/       /'
  fi
}

echo "== autotest narzędzi na wzorcach ($FIX)"
expect pass "terraform fmt: poprawny wzorzec" tf_fmt "$FIX/dobry/terraform"
expect pass "terraform validate: poprawny wzorzec" tf_validate "$FIX/dobry/terraform"
expect pass "tflint: poprawny wzorzec" tf_lint "$FIX/dobry/terraform"
expect pass "trivy config: poprawny wzorzec" trivy_config "$FIX/dobry/terraform"
expect pass "ansible-lint: poprawny wzorzec" ansible_lint "$FIX/dobry/ansible/site.yml"
expect reject "terraform fmt: zły format" tf_fmt "$FIX/zly/fmt"
expect reject "terraform validate: niezadeklarowana zmienna" tf_validate "$FIX/zly/validate"
expect reject "tflint: nieużywana zmienna" tf_lint "$FIX/zly/tflint"
expect reject "trivy config: SSH otwarty dla 0.0.0.0/0" trivy_config "$FIX/zly/trivy"
expect reject "ansible-lint: zadanie bez nazwy, command bez changed_when" ansible_lint "$FIX/zly/ansible/site.yml"

echo "== IaC projektu"
# Moduły główne Terraform (ADR-0007) i playbook Ansible. Dochodzą w kolejnych PR-ach E3;
# do tego czasu sprawdzenie jest czerwone (plan w docs/stan-pracy.md).
for dir in infra/terraform/oci infra/terraform/cloudflare; do
  if ! ls "$dir"/*.tf >/dev/null 2>&1; then bad "brak modułu Terraform: $dir/*.tf"; continue; fi
  expect pass "terraform fmt: $dir" tf_fmt "$dir"
  expect pass "terraform validate: $dir" tf_validate "$dir"
  expect pass "tflint: $dir" tf_lint "$dir"
  expect pass "trivy config: $dir" trivy_config "$dir"
done
if [ -f infra/ansible/site.yml ]; then
  expect pass "ansible-lint: infra/ansible" ansible_lint infra/ansible/site.yml
else
  bad "brak playbooka Ansible: infra/ansible/site.yml"
fi

[ "$fail" -eq 0 ] && echo "iac-lint: OK" || echo "iac-lint: BŁĘDY (wyżej)"
exit "$fail"
