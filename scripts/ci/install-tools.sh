#!/usr/bin/env bash
# scripts/ci/install-tools.sh KATALOG: instaluje narzędzia bramek do KATALOG/bin
# w przypiętych wersjach, sprawdzając sumy SHA-256 (Linux x64 i macOS arm64).
# Sumy pochodzą z plików checksums wydawców (gitleaks, sops, actionlint, hadolint);
# dla age, shellcheck i zizmor (bez pliku sum; age ma tylko dowody .proof) z pierwszego
# pobrania 22.11.2026. Każda suma musi mieć 64 znaki i być sprawdzona w trybie --strict.
set -euo pipefail
# Ścieżka bezwzględna: skrypt robi `cd` do KATALOG, więc ścieżka względna (np. `.tools`
# z `make tools`) wskazywałaby potem w złe miejsce.
dest="$(mkdir -p "${1:?Użycie: install-tools.sh KATALOG}/bin" && cd "$1" && pwd)"
cd "$dest"
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64)
    gl=gitleaks_8.30.1_linux_x64.tar.gz;          gl_sha=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
    so=sops-v3.13.3.linux.amd64;                  so_sha=e5bec3346a873ae91d871550f3e698c1aad962aff462a080e40f25fde17fef6b
    ag=age-v1.3.2-linux-amd64.tar.gz;             ag_sha=cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10
    sc=shellcheck-v0.11.0.linux.x86_64.tar.xz;    sc_sha=8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198
    hd=hadolint-linux-x86_64;                     hd_sha=6bf226944684f56c84dd014e8b979d27425c0148f61b3bd99bcc6f39e9dc5a47
    al=actionlint_1.7.12_linux_amd64.tar.gz;      al_sha=8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8
    zz=zizmor-x86_64-unknown-linux-gnu.tar.gz;    zz_sha=bb110cc765eca9cd7efb2e284a956be5974c60027b0970f16397d86208a9957b
    ;;
  Darwin-arm64)
    gl=gitleaks_8.30.1_darwin_arm64.tar.gz;       gl_sha=b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5
    so=sops-v3.13.3.darwin.arm64;                 so_sha=b97c0d434aab577dc40310e8d22ff9e45eef4c80638ab978daae9b4681c59286
    ag=age-v1.3.2-darwin-arm64.tar.gz;            ag_sha=e2020b073c44f692685a24d6abc378817eb81ffaaf49fd0531ef8565f767f2f5
    sc=shellcheck-v0.11.0.darwin.aarch64.tar.xz;  sc_sha=56affdd8de5527894dca6dc3d7e0a99a873b0f004d7aabc30ae407d3f48b0a79
    hd=hadolint-macos-arm64;                      hd_sha=3625e2e9f43dcfe7bd38738a5f5520ed50ce39ed28485266e6803dd7bc197b10
    al=actionlint_1.7.12_darwin_arm64.tar.gz;     al_sha=aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f
    zz=zizmor-aarch64-apple-darwin.tar.gz;        zz_sha=6efed18c4539a663fd3c851a2be9533fd8456c4e646d9416206da059154a0d3c
    ;;
  *) echo "Nieobsługiwany system: $(uname -s)-$(uname -m)"; exit 1 ;;
esac
gh=https://github.com
curl -sSfLo "$gl" "$gh/gitleaks/gitleaks/releases/download/v8.30.1/$gl"
curl -sSfLo "$so" "$gh/getsops/sops/releases/download/v3.13.3/$so"
curl -sSfLo "$ag" "$gh/FiloSottile/age/releases/download/v1.3.2/$ag"
curl -sSfLo "$sc" "$gh/koalaman/shellcheck/releases/download/v0.11.0/$sc"
curl -sSfLo "$hd" "$gh/hadolint/hadolint/releases/download/v2.14.0/$hd"
curl -sSfLo "$al" "$gh/rhysd/actionlint/releases/download/v1.7.12/$al"
curl -sSfLo "$zz" "$gh/zizmorcore/zizmor/releases/download/v1.32.0/$zz"
for h in "$gl_sha" "$so_sha" "$ag_sha" "$sc_sha" "$hd_sha" "$al_sha" "$zz_sha"; do
  [ "${#h}" -eq 64 ] || { echo "Niepoprawna suma SHA-256: '$h'"; exit 1; }
done
# --strict: wiersz z pustą lub uciętą sumą to błąd, a nie ostrzeżenie z kodem 0.
sum() { if command -v sha256sum >/dev/null; then sha256sum --strict -c -; else shasum -a 256 --strict -c -; fi; }
printf '%s  %s\n' "$gl_sha" "$gl" "$so_sha" "$so" "$ag_sha" "$ag" "$sc_sha" "$sc" \
  "$hd_sha" "$hd" "$al_sha" "$al" "$zz_sha" "$zz" | sum
tar -xzf "$gl" -C bin gitleaks
tar -xzf "$ag" --strip-components=1 -C bin age/age age/age-keygen
tar -xJf "$sc" --strip-components=1 -C bin shellcheck-v0.11.0/shellcheck
tar -xzf "$al" -C bin actionlint
install -m 0755 "$so" bin/sops
install -m 0755 "$hd" bin/hadolint
tar -xzf "$zz" -C bin zizmor
bin/zizmor --version | grep -q '1.32.0' || { echo "zizmor: zła wersja"; exit 1; }
echo "Zainstalowano w $dest/bin:"; ls "$dest/bin"
