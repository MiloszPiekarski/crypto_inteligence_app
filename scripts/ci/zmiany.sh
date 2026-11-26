#!/usr/bin/env bash
# scripts/ci/zmiany.sh: które joby CI potrzebne w tym przebiegu (ADR-0008, punkt 7).
# W PR (EVENT=pull_request, BASE = commit bazy) patrzy na zmienione pliki:
# - obrazy (build i Trivy amd64 i arm64): tylko przy zmianie Dockerfile, .dockerignore,
#   pyproject.toml, uv.lock albo ci.yml;
# - macOS (bramki z bash 3.2 i narzędziami BSD): tylko przy zmianie *.sh, Makefile,
#   scripts/, gates/, infra/ albo ci.yml.
# Na main, przy ręcznym uruchomieniu i przy każdym błędzie: wszystko (bezpieczna strona).
# Wynik w $GITHUB_OUTPUT: obrazy=true|false, systemy=<lista JSON systemów bramek>.
set -euo pipefail

obrazy=true
macos=true
if [ "${EVENT:-}" = "pull_request" ]; then
  files="$(git diff --name-only "${BASE:?brak BASE (commit bazy PR)}" HEAD)"
  obrazy=false
  macos=false
  while IFS= read -r f; do
    case "$f" in
      Dockerfile | */Dockerfile | .dockerignore | */.dockerignore | pyproject.toml | */pyproject.toml | uv.lock | .github/workflows/ci.yml)
        obrazy=true
        ;;
    esac
    case "$f" in
      *.sh | Makefile | scripts/* | gates/* | infra/* | .github/workflows/ci.yml)
        macos=true
        ;;
    esac
  done <<<"$files"
fi

if [ "$macos" = true ]; then
  systemy='["ubuntu-latest","macos-15"]'
else
  systemy='["ubuntu-latest"]'
fi
out="${GITHUB_OUTPUT:?brak GITHUB_OUTPUT}"
{
  echo "obrazy=$obrazy"
  echo "systemy=$systemy"
} >>"$out"
echo "obrazy: $obrazy, bramki na: $systemy"
