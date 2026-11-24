#!/usr/bin/env bash
# scripts/ci/wait-for-ci.sh SHA: czeka, aż przebieg ci.yml (push na main) dla commitu SHA skończy
# job `ci-ok` (deploy-staging.yml: wdrażamy tylko commit z zielonym CI, czyli z obrazem
# zbudowanym, przeskanowanym i podpisanym w GHCR). Kod 0 tylko przy `ci-ok` = success.
# Nie patrzymy na wynik całego przebiegu: job bramki etapu w toku jest poza ci-ok.
# Wymaga GH_TOKEN (actions: read) i GH_REPO. Limit: WAIT_MAX_SECONDS (domyślnie 2700).
set -euo pipefail
sha="${1:?Użycie: wait-for-ci.sh SHA}"
deadline=$(( $(date +%s) + ${WAIT_MAX_SECONDS:-2700} ))
while :; do
  run_id="$(gh run list --workflow ci.yml --commit "$sha" --event push --branch main \
    --json databaseId --jq '.[0].databaseId // empty' 2>/dev/null || true)"
  if [ -n "$run_id" ]; then
    result="$(gh api "repos/$GH_REPO/actions/runs/$run_id/jobs?per_page=100" \
      --jq '[.jobs[] | select(.name == "ci-ok")][0] | "\(.status) \(.conclusion)"' 2>/dev/null || true)"
    case "$result" in
      "completed success") echo "CI $run_id: ci-ok = success"; exit 0 ;;
      completed\ *) echo "CI $run_id: ci-ok = ${result#completed }; nie wdrażam"; exit 1 ;;
    esac
  fi
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "CI dla $sha nie skończyło się w limicie; nie wdrażam"; exit 1
  fi
  sleep 30
done
