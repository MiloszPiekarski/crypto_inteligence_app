#!/usr/bin/env bash
# scripts/g3_rebuild.sh: odtworzenie staging od zera (F-01; dowód lokalny G3 `rebuild`,
# gates/G3.yaml: < 30 min, 0 ręcznych kroków). Uruchamia WŁAŚCICIEL na Macu, na czystym `main`
# równym origin/main, z kluczami chmury w środowisku (.env.local: OCI, Cloudflare, Tailscale).
#
# Przed startem zegara: plan Terraform (zastąpienie maszyn i wolumenu danych) i jedno „tak”.
# Potem bez udziału człowieka:
#   1. stare węzły goatcash-staging/goatcash-executor usunięte z Tailscale (nazwy MagicDNS);
#   2. Terraform w dwóch fazach: (a) usunięcie A1 i wolumenu danych oraz czekanie, aż Oracle
#      zwolni limit wolumenów; (b) nowe A1, wolumen, executor i klucze Tailscale, z kontrolą,
#      że plan usuwa tylko zastępowane zasoby (A1 Always Free: najpierw usunięcie; ADR-0007);
#   3. rekordy DNS api./app. na nowe IP (Cloudflare, tylko te dwa zasoby);
#   4. czekanie na węzły w Tailscale (cloud-init), potem ansible-staging.yml;
#   5. ponowienie ostatniego wdrożenia HEAD (deploy-staging.yml): pusty wolumen, więc deploy.sh
#      odtwarza bazę z kopii w R2, migracje, test dymny;
#   6. https://api.goatcash.app/v1/health z internetu.
# Raport: docs/gates/G3/rebuild-<czas>.log (nagłówek i ostatnia linia wg gates/G3.yaml).
# Wymaga: terraform, gh (zalogowany), curl, python3; zmiennych TAILSCALE_OAUTH_CLIENT_ID,
# TAILSCALE_OAUTH_CLIENT_SECRET (klient z zakresami auth_keys i devices:core,
# jedyny tag: tag:goatcash-terraform, właściciel tagów serwerów; ADR-0007 pkt 6).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
if [ -d .tools/bin ]; then PATH="$PWD/.tools/bin:$PATH"; fi

die() { echo "FAIL $*"; exit 1; }
[ -z "$(git status --porcelain)" ] || die "katalog roboczy nie jest czysty"
git fetch -q origin main || die "git fetch"
SHA="$(git rev-parse HEAD)"
[ "$SHA" = "$(git rev-parse origin/main)" ] || die "HEAD to nie origin/main"
for v in TAILSCALE_OAUTH_CLIENT_ID TAILSCALE_OAUTH_CLIENT_SECRET CLOUDFLARE_ACCOUNT_ID; do
  [ -n "${!v:-}" ] || die "brak zmiennej $v (.env.local)"
done
[ -f infra/terraform/oci/staging.tfvars ] || die "brak infra/terraform/oci/staging.tfvars (lokalny, poza git)"
# Namespace bucketu stanu (częściowa konfiguracja backendu) i zmienne modułu cloudflare.
NS="$(oci os ns get --query data --raw-output)" || die "oci os ns get"
export TF_VAR_state_namespace="$NS" TF_VAR_account_id="$CLOUDFLARE_ACCOUNT_ID"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p docs/gates/G3
REPORT="docs/gates/G3/rebuild-$TS.log"
exec > >(tee "$REPORT") 2>&1
echo "Raport G3 rebuild | commit $SHA | $TS | local"

OCI=infra/terraform/oci
REPLACE=(-replace=oci_core_instance.platform -replace=oci_core_instance.executor
         -replace=oci_core_volume.data -replace=oci_core_volume_attachment.data
         -replace=tailscale_tailnet_key.platform -replace=tailscale_tailnet_key.executor)
PLAN="$(mktemp)"
trap 'rm -f "$PLAN" "$PLAN.txt"' EXIT
terraform -chdir="$OCI" init -input=false -backend-config="namespace=$NS" >/dev/null || die "terraform init"
terraform -chdir="$OCI" plan -input=false -no-color -var-file=staging.tfvars "${REPLACE[@]}" -out="$PLAN" > "$PLAN.txt" ||
  { tail -20 "$PLAN.txt"; die "terraform plan"; }
grep -E '^Plan:' "$PLAN.txt" || die "brak podsumowania planu"
grep -E '# .* (will be|must be) (destroyed|replaced)' "$PLAN.txt" | sed 's/^ */  /'
echo "Wpisz tak, żeby zastąpić maszyny i wolumen danych (dane wrócą z kopii w R2):"
read -r answer < /dev/tty
[ "$answer" = tak ] || die "przerwane przez właściciela"

START="$(date +%s)"
step() { echo "== [$(( $(date +%s) - START )) s] $*"; }

ts_token() {
  curl -fsS -d "client_id=$TAILSCALE_OAUTH_CLIENT_ID" -d "client_secret=$TAILSCALE_OAUTH_CLIENT_SECRET" \
    https://api.tailscale.com/api/v2/oauth/token |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
}
ts_devices() { # wypisuje "id nazwa online" dla węzłów goatcash-staging / goatcash-executor
  curl -fsS -H "Authorization: Bearer $1" "https://api.tailscale.com/api/v2/tailnet/-/devices?fields=all" |
    python3 -c 'import json,sys
for d in json.load(sys.stdin)["devices"]:
    if d["hostname"] in ("goatcash-staging", "goatcash-executor"):
        print(d["nodeId"], d["hostname"], str(d.get("connectedToControl", False)).lower())'
}

step "1. usunięcie starych węzłów z Tailscale"
TOKEN="$(ts_token)" || die "token Tailscale (OAuth)"
OLD="$(ts_devices "$TOKEN")" || die "lista węzłów Tailscale"
while read -r id name _; do
  [ -n "$id" ] || continue
  curl -fsS -X DELETE -H "Authorization: Bearer $TOKEN" "https://api.tailscale.com/api/v2/device/$id" >/dev/null ||
    die "usunięcie węzła $name (klient OAuth potrzebuje zakresu devices:core)"
  echo "  usunięto $name"
done <<<"$OLD"

# Oracle usuwa wolumen asynchronicznie, a wolumen w stanie TERMINATING nadal zajmuje limit
# (200 GB, 2 wolumeny blokowe). Jedno `apply -replace` tworzyło nowy wolumen, zanim stary
# zniknął: 400-LimitExceeded (próba 25.11.2026). Dlatego dwie fazy:
#   2a. usunięcie A1, podłączenia i wolumenu, czekanie na stan TERMINATED wolumenu;
#   2b. nowy plan (A1, wolumen i podłączenie tworzone, executor i klucze Tailscale
#       zastępowane) z kontrolą, że usuwa wyłącznie te zasoby, i jego wykonanie.
step "2a. usunięcie A1 i wolumenu danych (czekanie na zwolnienie limitu)"
VOL_ID="$(terraform -chdir="$OCI" state show -no-color oci_core_volume.data |
  sed -n 's/^ *id *= *"\(ocid1\.volume[^"]*\)".*/\1/p' | head -1)"
[ -n "$VOL_ID" ] || die "brak id wolumenu danych w stanie Terraform"
terraform -chdir="$OCI" destroy -input=false -no-color -auto-approve -var-file=staging.tfvars \
  -target=oci_core_volume_attachment.data -target=oci_core_volume.data \
  -target=oci_core_instance.platform | tail -1
[ "${PIPESTATUS[0]}" -eq 0 ] || die "usunięcie A1 i wolumenu"
vstate=""
for _ in $(seq 1 90); do
  vstate="$(oci bv volume get --volume-id "$VOL_ID" --query 'data."lifecycle-state"' --raw-output 2>/dev/null || true)"
  [ "$vstate" = TERMINATED ] && break
  sleep 10
done
[ "$vstate" = TERMINATED ] || die "stary wolumen nie został usunięty w 15 min (stan: ${vstate:-?})"
echo "  stary wolumen: TERMINATED"

step "2b. terraform apply (A1, wolumen, executor, klucze Tailscale)"
PLAN2="$(mktemp)"
terraform -chdir="$OCI" plan -input=false -no-color -var-file=staging.tfvars \
  -replace=oci_core_instance.executor -replace=tailscale_tailnet_key.platform \
  -replace=tailscale_tailnet_key.executor -out="$PLAN2" > "$PLAN2.txt" ||
  { tail -20 "$PLAN2.txt"; die "terraform plan (faza 2b)"; }
grep -E '^Plan:' "$PLAN2.txt"
# Usuwać wolno wyłącznie zastępowane: executor i dwa klucze Tailscale.
removed="$(grep -E '# .* (will be destroyed|must be replaced|will be replaced)' "$PLAN2.txt" |
  sed -E 's/^ *# ([^ ]+) .*/\1/' | sort | tr '\n' ' ')"
[ "$removed" = "oci_core_instance.executor tailscale_tailnet_key.executor tailscale_tailnet_key.platform " ] ||
  { rm -f "$PLAN2" "$PLAN2.txt"; die "plan 2b usuwa coś nieoczekiwanego: $removed"; }
terraform -chdir="$OCI" apply -input=false -no-color "$PLAN2" | tail -3
[ "${PIPESTATUS[0]}" -eq 0 ] || { rm -f "$PLAN2" "$PLAN2.txt"; die "terraform apply (faza 2b)"; }
rm -f "$PLAN2" "$PLAN2.txt"

step "3. DNS api./app. na nowe IP (Cloudflare)"
terraform -chdir=infra/terraform/cloudflare init -input=false -backend-config="namespace=$NS" >/dev/null ||
  die "terraform init cloudflare"
terraform -chdir=infra/terraform/cloudflare apply -input=false -no-color -auto-approve \
  -target=cloudflare_dns_record.api -target=cloudflare_dns_record.app | tail -2
[ "${PIPESTATUS[0]}" -eq 0 ] || die "terraform apply cloudflare (DNS)"
# Adres do skanu z zewnątrz (external-scan.yml) po zmianie IP.
IP="$(terraform -chdir="$OCI" output -raw platform_public_ip)" || die "terraform output"
gh variable set STAGING_PLATFORM_PUBLIC_IP --env staging-readonly --body "$IP" || die "zmienna STAGING_PLATFORM_PUBLIC_IP"
echo "  platforma: $IP"

step "4. węzły w Tailscale (cloud-init), potem Ansible"
online=""
for _ in $(seq 1 60); do
  online="$(ts_devices "$TOKEN" | awk '$3 == "true" {print $2}' | sort | tr '\n' ' ')"
  [ "$online" = "goatcash-executor goatcash-staging " ] && break
  sleep 10
done
[ "$online" = "goatcash-executor goatcash-staging " ] || die "węzły nie pojawiły się w Tailscale ($online)"
echo "  online: $online"

run_and_watch() { # workflow: uruchamia na main i czeka na wynik
  local before id
  before="$(gh run list --workflow "$1" --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
  gh workflow run "$1" --ref main || return 1
  for _ in $(seq 1 30); do
    id="$(gh run list --workflow "$1" --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
    [ "$id" != "$before" ] && break
    sleep 4
  done
  [ "$id" != "$before" ] || return 1
  echo "  przebieg $id"
  gh run watch "$id" --exit-status --interval 15 >/dev/null
}
run_and_watch ansible-staging.yml || die "ansible-staging.yml"

step "5. wdrożenie HEAD (deploy-staging.yml): odtworzenie bazy z R2, migracje, test dymny"
DEPLOY="$(gh run list --workflow deploy-staging.yml --branch main --event push --limit 20 \
  --json databaseId,headSha --jq "[.[] | select(.headSha == \"$SHA\")][0].databaseId // empty")"
[ -n "$DEPLOY" ] || die "brak przebiegu deploy-staging.yml dla $SHA"
gh run rerun "$DEPLOY" || die "ponowienie wdrożenia $DEPLOY"
sleep 10
gh run watch "$DEPLOY" --exit-status --interval 15 >/dev/null || die "deploy-staging.yml (przebieg $DEPLOY)"
echo "  przebieg $DEPLOY"

step "6. /v1/health z internetu"
body="$(curl -fsS --max-time 10 https://api.goatcash.app/v1/health || true)"
grep -q '"status":"ok"' <<<"$body" || die "/v1/health"
echo "  /v1/health: ok"

echo "== G3 rebuild (local): PASS, $(( $(date +%s) - START )) s, 0 manual steps =="
