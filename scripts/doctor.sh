#!/usr/bin/env bash
# scripts/doctor.sh – E0 readiness check for gate G0 (GoatCash).
# Checks tool versions, AI provider keys, market data sources and Oracle access.
# Never prints secret values. Exit code 0 = all PASS, 1 = at least one FAIL.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env.local"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
UA="goatcash-doctor/1.0"
PASS=0; FAIL=0

ok()      { printf '  \033[32mPASS\033[0m %s\n' "$1"; PASS=$((PASS+1)); }
bad()     { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAIL=$((FAIL+1)); }
section() { printf '\n== %s ==\n' "$1"; }

# version_ge CURRENT MIN -> true if CURRENT >= MIN
version_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }
first_version() { grep -Eo '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1; }

# check_tool NAME MIN_VERSION COMMAND...
check_tool() {
  local name="$1" min="$2" out ver; shift 2
  if ! out="$("$@" 2>&1)"; then bad "$name: not installed or not working"; return; fi
  ver="$(printf '%s' "$out" | first_version)"
  if [ -z "$ver" ]; then bad "$name: cannot read version"; return; fi
  if version_ge "$ver" "$min"; then ok "$name $ver (min $min)"; else bad "$name $ver is below min $min"; fi
}

# http ARGS... -> prints HTTP status, body saved to $TMP/body
# curl sam wypisuje 000 przy błędzie sieci; stare body jest usuwane, żeby komunikat
# błędu nie pochodził z odpowiedzi poprzedniego dostawcy.
http() {
  local code
  rm -f "$TMP/body"
  code="$(curl -sS -A "$UA" -o "$TMP/body" -w '%{http_code}' --max-time 30 "$@" 2>/dev/null)" || true
  printf '%s' "${code:-000}"
}
api_error() { jq -r '(.error.message // .error // .message // empty) | tostring' "$TMP/body" 2>/dev/null | head -c 200; }

# ---------------------------------------------------------------------------
section "1. Tool versions"
check_tool "macOS"          "15.0"  sw_vers -productVersion
check_tool "git"            "2.40"  git --version
check_tool "gh"             "2.40"  gh --version
check_tool "uv"             "0.5"   uv --version
check_tool "Python (uv)"    "3.12"  uv python find 3.12
check_tool "Node.js"        "24.0"  node --version
node_major="$(node --version 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/')"
if [ "${node_major:-0}" = "24" ]; then ok "Node.js is the 24 LTS line"; else bad "Node.js major is ${node_major:-none}, expected 24 (LTS)"; fi
check_tool "pnpm"           "9.0"   pnpm --version
check_tool "Terraform"      "1.9"   terraform version
check_tool "Ansible"        "2.17"  ansible --version
check_tool "sops"           "3.9"   sops --version
check_tool "age"            "1.2"   age --version
check_tool "pre-commit"     "3.7"   pre-commit --version
check_tool "OCI CLI"        "3.40"  oci --version
check_tool "jq"             "1.6"   jq --version
check_tool "Docker CLI"     "27.0"  docker --version
check_tool "Docker engine"  "27.0"  docker info --format '{{.ServerVersion}}'
check_tool "VS Code"        "1.90"  code --version
check_tool "Claude Code"    "2.0"   claude --version

# ---------------------------------------------------------------------------
section "2. Local secrets file (.env.local)"
if [ -f "$ENV_FILE" ]; then
  # GNU stat (Linux) rozumie -f inaczej (system plików), więc wybieramy wariant po systemie.
  if [ "$(uname -s)" = "Darwin" ]; then perms="$(stat -f '%Lp' "$ENV_FILE")"; else perms="$(stat -c '%a' "$ENV_FILE")"; fi
  if [ "$perms" = "600" ]; then ok ".env.local permissions 600"; else bad ".env.local permissions $perms (fix: chmod 600 .env.local)"; fi
  if git -C "$ROOT" check-ignore -q .env.local 2>/dev/null; then ok ".env.local is ignored by git"; else bad ".env.local is NOT ignored by git (add it to .gitignore)"; fi
  set -a; # shellcheck disable=SC1090
  . "$ENV_FILE"; set +a
else
  bad ".env.local not found in $ROOT"
fi
for v in ANTHROPIC_API_KEY GEMINI_API_KEY OPENROUTER_API_KEY COINGECKO_DEMO_API_KEY; do
  if [ -n "${!v:-}" ]; then ok "$v is set (value hidden)"; else bad "$v is empty or missing"; fi
done

# ---------------------------------------------------------------------------
section "3. AI providers (one minimal request each)"
code=$(http https://api.anthropic.com/v1/messages \
  -H "x-api-key: ${ANTHROPIC_API_KEY:-}" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" \
  -d '{"model":"claude-haiku-5-5","max_tokens":10,"messages":[{"role":"user","content":"Reply with the word OK."}]}')
if [ "$code" = 200 ] && jq -e '.content[0].text | length > 0' "$TMP/body" >/dev/null 2>&1; then
  ok "Anthropic: HTTP 200, model answered: $(jq -r '.content[0].text' "$TMP/body" | head -c 40)"
else bad "Anthropic: HTTP $code $(api_error)"; fi

code=$(http "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200" -H "x-goog-api-key: ${GEMINI_API_KEY:-}")
gem_ok=0; gem_last=""
if [ "$code" = 200 ]; then
  # Newest "flash" models first (version-sorted, descending); skip special variants.
  for gmodel in $(jq -r '.models[] | select(.supportedGenerationMethods | index("generateContent")) | .name
                         | select(test("flash")) | select(test("tts|image|live|embedding|exp") | not)' "$TMP/body" \
                  | sort -rV | head -5); do
    code=$(http "https://generativelanguage.googleapis.com/v1beta/${gmodel}:generateContent" \
      -H "x-goog-api-key: ${GEMINI_API_KEY:-}" -H "content-type: application/json" \
      -d '{"contents":[{"parts":[{"text":"Reply with the word OK."}]}]}')
    if [ "$code" = 200 ] && jq -e '.candidates[0].content.parts[0].text | length > 0' "$TMP/body" >/dev/null 2>&1; then
      ok "Gemini ($gmodel): HTTP 200, model answered"; gem_ok=1; break
    fi
    gem_last="$gmodel: HTTP $code $(api_error)"
  done
  [ "$gem_ok" = 1 ] || bad "Gemini: no flash model answered (last: ${gem_last:-no flash models listed})"
else bad "Gemini: cannot list models (HTTP $code) $(api_error)"; fi

code=$(http https://openrouter.ai/api/v1/key -H "Authorization: Bearer ${OPENROUTER_API_KEY:-}")
if [ "$code" = 200 ]; then
  limit=$(jq -r '.data.limit // "none"' "$TMP/body")
  # Porównanie liczbowe (np. 5.0 <= 5), nie wersji.
  if [ "$limit" != "none" ] && [ "$limit" != "null" ] && awk -v l="$limit" 'BEGIN { exit !(l + 0 <= 5) }'; then ok "OpenRouter: key valid, credit limit $limit USD (max 5)"
  else bad "OpenRouter: key credit limit is '$limit', expected 5 USD or less"; fi
else bad "OpenRouter: key check HTTP $code $(api_error)"; fi
code=$(http https://openrouter.ai/api/v1/models)
or_ok=0
if [ "$code" = 200 ]; then
  for m in $(jq -r '[.data[].id | select(endswith(":free"))] | .[0:5][]' "$TMP/body"); do
    code=$(http https://openrouter.ai/api/v1/chat/completions \
      -H "Authorization: Bearer ${OPENROUTER_API_KEY:-}" -H "content-type: application/json" \
      -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the word OK.\"}]}")
    if [ "$code" = 200 ] && jq -e '.choices[0].message' "$TMP/body" >/dev/null 2>&1; then
      ok "OpenRouter ($m, free model): HTTP 200, model answered"; or_ok=1; break
    fi
  done
fi
[ "$or_ok" = 1 ] || bad "OpenRouter: no free model answered (last HTTP $code) $(api_error)"

# ---------------------------------------------------------------------------
section "4. Market data: CoinGecko + exchanges"
code=$(http "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd" -H "x-cg-demo-api-key: ${COINGECKO_DEMO_API_KEY:-}")
if [ "$code" = 200 ] && jq -e '.bitcoin.usd > 0' "$TMP/body" >/dev/null 2>&1; then
  ok "CoinGecko Demo: BTC = $(jq -r '.bitcoin.usd' "$TMP/body") USD"
else bad "CoinGecko Demo: HTTP $code $(api_error)"; fi

code=$(http "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1H&limit=1")
if [ "$code" = 200 ] && jq -e '.code == "0" and (.data | length > 0)' "$TMP/body" >/dev/null 2>&1; then ok "OKX: BTC-USDT 1h candle received"
else bad "OKX: HTTP $code (note region block, pick another exchange before E4)"; fi

code=$(http "https://api.bybit.com/v5/market/kline?category=spot&symbol=BTCUSDT&interval=60&limit=1")
if [ "$code" = 200 ] && jq -e '.retCode == 0 and (.result.list | length > 0)' "$TMP/body" >/dev/null 2>&1; then ok "Bybit: BTCUSDT 1h candle received"
else bad "Bybit: HTTP $code (note region block, pick another exchange before E4)"; fi

code=$(http "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600")
if [ "$code" = 200 ] && jq -e 'type == "array" and length > 0' "$TMP/body" >/dev/null 2>&1; then ok "Coinbase: BTC-USD 1h candles received"
else bad "Coinbase: HTTP $code (note region block, pick another exchange before E4)"; fi

code=$(http "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60")
if [ "$code" = 200 ] && jq -e '(.error | length == 0) and (.result | keys | length > 1)' "$TMP/body" >/dev/null 2>&1; then ok "Kraken: XBTUSD 1h candles received"
else bad "Kraken: HTTP $code (note region block, pick another exchange before E4)"; fi

# ---------------------------------------------------------------------------
section "5. Oracle Cloud (IAM user key)"
if oci iam region-subscription list --output json > "$TMP/oci" 2>"$TMP/oci_err"; then
  home=$(jq -r '.data[] | select(."is-home-region") | ."region-name"' "$TMP/oci")
  case "$home" in eu-*) ok "Oracle: home region $home (EU)";; *) bad "Oracle: home region '$home' is not in the EU";; esac
else bad "Oracle: CLI call failed: $(head -c 200 "$TMP/oci_err")"; fi
oci_user=$(awk -F= '/^user[[:space:]]*=/{gsub(/[[:space:]]/,"",$2); print $2; exit}' "$HOME/.oci/config" 2>/dev/null)
if [ -n "$oci_user" ] && oci iam user get --user-id "$oci_user" --output json > "$TMP/ociu" 2>/dev/null; then
  uname=$(jq -r '.data.name' "$TMP/ociu")
  case "$uname" in *terraform*) ok "Oracle: CLI uses the IAM user '$uname', not the root admin";; *) bad "Oracle: CLI uses '$uname', expected the terraform IAM user";; esac
else bad "Oracle: cannot read the CLI user from ~/.oci/config"; fi

# ---------------------------------------------------------------------------
printf '\n== Summary: %d PASS, %d FAIL ==\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
