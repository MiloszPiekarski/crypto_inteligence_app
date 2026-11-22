#!/usr/bin/env bash
# scripts/github-setup.sh – ustawienia repozytorium GitHub z E1.6 jako kod.
# Uruchom PO pierwszym zielonym przebiegu CI (wtedy istnieje check "ci-ok"):
#   ./scripts/github-setup.sh
# Wymaga: gh zalogowany jako właściciel repo.
set -euo pipefail
REPO="${REPO:-MiloszPiekarski/crypto_inteligence_app}"
say() { printf '\n== %s\n' "$1"; }

say "Ustawienia scalania: tylko squash (liniowa historia), usuwanie gałęzi po scaleniu"
gh api -X PATCH "repos/$REPO" --silent \
  -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false \
  -F delete_branch_on_merge=true -F allow_auto_merge=false

say "Secret Scanning + Push Protection (warstwa 2)"
gh api -X PATCH "repos/$REPO" --silent --input - <<'JSON'
{"security_and_analysis": {
  "secret_scanning": {"status": "enabled"},
  "secret_scanning_push_protection": {"status": "enabled"}
}}
JSON

say "Dependabot: alerty i aktualizacje bezpieczeństwa"
gh api -X PUT "repos/$REPO/vulnerability-alerts" --silent
gh api -X PUT "repos/$REPO/automated-security-fixes" --silent

say "Prywatne zgłaszanie podatności (SECURITY.md)"
gh api -X PUT "repos/$REPO/private-vulnerability-reporting" --silent

say "CodeQL: konfiguracja domyślna (Python, JavaScript/TypeScript, Actions)"
gh api -X PATCH "repos/$REPO/code-scanning/default-setup" --silent \
  -f state=configured -f query_suite=default

say "Etykiety etapów i typów"
for l in E0 E1 E2 E3 E4 E5 E6 E7 E8 E9 E10 E10a E11 E11a E12a E12b E13 E14a E14b E14c E15 E16 E17 E18; do
  gh label create "$l" --repo "$REPO" --color 1f6feb --description "Etap $l z roadmapy" --force >/dev/null
done
gh label create task --repo "$REPO" --color 0e8a16 --description "Zadanie z roadmapy" --force >/dev/null
gh label create bug --repo "$REPO" --color d73a4a --description "Błąd" --force >/dev/null
gh label create dependencies --repo "$REPO" --color 0366d6 --description "Aktualizacje zależności" --force >/dev/null

say "Ochrona main (ruleset): PR, zielone ci-ok, podpisy, liniowa historia, zakaz force-push i usunięcia"
existing=$(gh api "repos/$REPO/rulesets" --jq '.[] | select(.name=="main-protection") | .id' || true)
method=POST; path="repos/$REPO/rulesets"
if [ -n "$existing" ]; then method=PUT; path="repos/$REPO/rulesets/$existing"; fi
gh api -X "$method" "$path" --silent --input - <<'JSON'
{
  "name": "main-protection",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "required_linear_history"},
    {"type": "required_signatures"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": true,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": true,
      "allowed_merge_methods": ["squash"]
    }},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": true,
      "do_not_enforce_on_create": false,
      "required_status_checks": [{"context": "ci-ok", "integration_id": 15368}]
    }}
  ]
}
JSON

say "Podsumowanie"
gh api "repos/$REPO" --jq '{secret_scanning: .security_and_analysis.secret_scanning.status, push_protection: .security_and_analysis.secret_scanning_push_protection.status, squash_only: (.allow_squash_merge and (.allow_merge_commit|not) and (.allow_rebase_merge|not))}'
gh api "repos/$REPO/rulesets" --jq '.[] | {name, enforcement}'
echo "Gotowe."
