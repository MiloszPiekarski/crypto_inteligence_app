#!/usr/bin/env bash
# scripts/audit.sh (make audit): statyczna kontrola tego, czego nie sprawdzają ruff/Biome:
#   skrypty bash (shellcheck), Dockerfile (hadolint), poprawność workflowów (actionlint),
#   bezpieczeństwo GitHub Actions (zizmor: przypięcie akcji, wycieki poświadczeń, wstrzyknięcia).
# Narzędzia w tych samych przypiętych wersjach co CI: `make tools` (instaluje do .tools/bin).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
if [ -d .tools/bin ]; then PATH="$PWD/.tools/bin:$PATH"; fi
fail=0
need() { command -v "$1" >/dev/null || { echo "Brak narzędzia: $1 (uruchom: make tools)"; fail=1; }; }
for t in shellcheck hadolint actionlint zizmor; do need "$t"; done
[ "$fail" -eq 0 ] || exit 1
run() { echo "== $1"; shift; "$@" || fail=1; }
# Listy plików z gita, żeby nowy skrypt albo Dockerfile nie wypadł z kontroli.
sh_files=(); while IFS= read -r f; do sh_files+=("$f"); done < <(git ls-files '*.sh')
dockerfiles=(); while IFS= read -r f; do dockerfiles+=("$f"); done < <(git ls-files '*Dockerfile')
# ${a[@]+"${a[@]}"}: pusta tablica w bash 3.2 z `set -u` dawałaby błąd „unbound variable”.
run shellcheck shellcheck -x -S warning ${sh_files[@]+"${sh_files[@]}"}
run hadolint hadolint ${dockerfiles[@]+"${dockerfiles[@]}"}
run actionlint actionlint
# Z tokenem (CI) zizmor sprawdza też online: czy SHA akcji należą do repozytorium i tagu
# z komentarza oraz znane podatne akcje. Bez tokenu (lokalnie) tylko audyty offline.
if [ -n "${GH_TOKEN:-}" ]; then run zizmor zizmor --no-progress .github
else run "zizmor (offline)" env -u GH_TOKEN -u GITHUB_TOKEN zizmor --offline --no-progress .github; fi
exit "$fail"
