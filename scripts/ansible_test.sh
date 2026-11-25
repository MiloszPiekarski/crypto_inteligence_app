#!/usr/bin/env bash
# make ansible-test (bramka G3 `ansible`): prawdziwy infra/ansible/site.yml na kontenerze
# „jak świeży serwer” (Ubuntu 24.04 z systemd, scripts/tests/fixtures/ansible-host) zamiast
# Molecule (plan E3, PR 10; rozliczenie E3). Wolumen danych to plik na pętli podpięty jako
# /dev/oracleoci/oraclevdb, tak jak w OCI. Sprawdza:
#   1. pierwszy przebieg bez błędów (restart pominięty: --skip-tags reboot);
#   2. drugi przebieg bez zmian (changed=0), bo odtworzenie od zera i ponowne przebiegi
#      muszą być bezpieczne;
#   3. wynik na „serwerze”: ufw (tylko Tailscale i 443 z Cloudflare), wolumen danych, Docker na
#      wolumenie, klucz age 0400 root, sudo deploy tylko dwa skrypty, timery kopii, Lynis 0.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
WORK="$(mktemp -d)"
NAME="gc-ansible-test-$$"
IMAGE="goatcash-ansible-host:test"
fail() { echo "  FAIL $*" >&2; exit 1; }
ok() { echo "  PASS $*"; }
cleanup() {
  docker exec "$NAME" sh -c 'swapoff -a; umount /mnt/swaptest; losetup -D' >/dev/null 2>&1 || true
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  rm -rf "$WORK" || true
}
trap cleanup EXIT

echo "== kontener Ubuntu 24.04 z systemd"
docker build -q -t "$IMAGE" scripts/tests/fixtures/ansible-host >/dev/null
docker run -d --name "$NAME" --hostname goatcash-staging --privileged --cgroupns=host \
  -v /sys/fs/cgroup:/sys/fs/cgroup:rw "$IMAGE" >/dev/null
state=""
for _ in $(seq 1 30); do
  state="$(docker exec "$NAME" systemctl is-system-running 2>/dev/null || true)"
  case "$state" in running|degraded) break ;; esac
  sleep 2
done
case "$state" in running|degraded) ;; *) fail "systemd w kontenerze: ${state:-brak odpowiedzi}" ;; esac
docker exec "$NAME" sh -c 'truncate -s 3G /data.img && L=$(losetup -f --show /data.img) &&
  mkdir -p /dev/oracleoci && ln -sf "$L" /dev/oracleoci/oraclevdb &&
  truncate -s 1G /swap.img && S=$(losetup -f --show /swap.img) && mkfs.ext4 -q "$S" &&
  mkdir -p /mnt/swaptest && mount "$S" /mnt/swaptest' || fail "wolumen danych i system plików na swap (pętle)"
ok "kontener z systemd ($state), wolumen danych jako /dev/oracleoci/oraclevdb"

export ANSIBLE_COLLECTIONS_PATH="$WORK/collections" ANSIBLE_NOCOLOR=1
uv run --frozen ansible-galaxy collection install -r infra/ansible/requirements.yml \
  -p "$WORK/collections" >/dev/null
uv run --frozen ansible-galaxy collection install \
  -r scripts/tests/fixtures/ansible-host/requirements-test.yml -p "$WORK/collections" >/dev/null
cat > "$WORK/inventory.yml" <<EOF
all:
  vars:
    ansible_connection: community.docker.docker
    ansible_user: root
    goatcash_admin_users: [ubuntu, deploy]
  children:
    platform:
      hosts:
        $NAME:
          swap_size_mb: 512
          # Linux nie przyjmuje pliku wymiany na overlayfs kontenera: plik na ext4 z pętli.
          base_swap_file: /mnt/swaptest/swapfile
    executor:
      hosts: {}
EOF
play() {
  (cd infra/ansible && GOATCASH_AGE_KEY_STAGING="wartosc-testowa-nie-klucz" \
    uv run --frozen ansible-playbook -i "$WORK/inventory.yml" site.yml --skip-tags reboot)
}

echo "== przebieg 1: site.yml"
play > "$WORK/run1.log" 2>&1 || { tail -30 "$WORK/run1.log" >&2; fail "pierwszy przebieg site.yml"; }
recap1="$(grep -E "^$NAME +:" "$WORK/run1.log" | tail -1)"
ok "pierwszy przebieg: ${recap1#*: }"

echo "== przebieg 2: bez zmian"
play > "$WORK/run2.log" 2>&1 || { tail -30 "$WORK/run2.log" >&2; fail "drugi przebieg site.yml"; }
recap2="$(grep -E "^$NAME +:" "$WORK/run2.log" | tail -1)"
grep -q 'changed=0 ' <<<"$recap2" || {
  grep -B3 '^changed:' "$WORK/run2.log" | grep '^TASK' >&2
  fail "drugi przebieg zmienia stan: ${recap2#*: }"
}
ok "drugi przebieg: changed=0 (idempotentny)"

echo "== stan serwera testowego"
check() { # opis komenda-w-kontenerze wzorzec
  local out
  out="$(docker exec "$NAME" bash -c "$2" 2>&1 || true)"
  grep -qE "$3" <<<"$out" || { printf '%s\n' "$out" | tail -10 >&2; fail "$1"; }
  ok "$1"
}
check "ufw aktywny, ruch z Tailscale dozwolony" "ufw status" "Status: active"
check "ufw: 443 tylko z zakresów Cloudflare" \
  "ufw status | grep -c '^443/tcp *ALLOW *[0-9]'" "^15$"
check "ufw: brak reguły dla 22 z internetu" "ufw status | grep -cE '^22(/tcp)? ' || true" "^0$"
check "wolumen danych w /srv/goatcash (ext4, etykieta goatcash-data)" \
  "findmnt -n -o FSTYPE,LABEL /srv/goatcash" "^ext4 +goatcash-data$"
check "Docker działa, dane na wolumenie" \
  "systemctl is-active docker && docker info --format '{{.DockerRootDir}}'" "/srv/goatcash/docker"
check "klucz age: 0400 root" "stat -c '%a %U' /etc/goatcash/age.key" "^400 root$"
check "deploy: sudo tylko render-env i Lynis" "sudo -l -U deploy | grep -c NOPASSWD" "^2$"
check "timery kopii (pełna i przyrostowa)" \
  "systemctl is-enabled goatcash-backup-full.timer goatcash-backup-incr.timer | tr '\n' ' '" "^enabled enabled"
check "plik wymiany aktywny" "swapon --show=NAME --noheadings" "^/mnt/swaptest/swapfile$"
check "SSH: bez logowania roota i haseł" "sshd -T | grep -E '^(permitrootlogin|passwordauthentication) '" \
  "passwordauthentication no"
check "Lynis: 0 ostrzeżeń" "/usr/local/bin/goatcash-lynis | tail -1" "^Lynis: 0 warnings"
echo "ansible-test: OK"
