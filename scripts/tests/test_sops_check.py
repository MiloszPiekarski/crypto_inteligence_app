"""Testy scripts/sops_check.py: jawny sekret w pliku *.enc.yaml musi zostać wykryty."""

from pathlib import Path

import sops_check

IV = "e9KIjXG2YeRmNKQbjb78v1eBzwrUd03g+C0ofz2Bloo="  # 32 bajty
TAG = "m/ysnGowjbuQteXRAwDX+g=="  # 16 bajtów
ENC = f"ENC[AES256_GCM,data:3q2+7w==,iv:{IV},tag:{TAG},type:str]"
AGE = "  age:\n    - recipient: age1test\n      enc: x\n"
SOPS = f"sops:\n{AGE}  mac: {ENC}\n  version: 3.13.3\n"


def test_encrypted_file_ok() -> None:
    text = f"key: {ENC}\nnested:\n  list:\n    - {ENC}\n{SOPS}"
    assert sops_check.problems(text) == []


def test_plaintext_value_detected() -> None:
    text = f"key: {ENC}\nnested:\n  token: jawny-sekret\n{SOPS}"
    assert sops_check.problems(text) == ["jawna wartość: nested.token"]


def test_plaintext_number_and_list_detected() -> None:
    text = f"port: 5432\nitems:\n  - {ENC}\n  - jawne\n{SOPS}"
    assert sops_check.problems(text) == ["jawna wartość: port", "jawna wartość: items[1]"]


def test_file_without_sops_block_detected() -> None:
    assert "nie jest zaszyfrowany" in sops_check.problems("api_key: sk-123\n")[0]


def test_fake_wrapped_plaintext_detected() -> None:
    """Uwaga z przeglądu PR #1: jawny tekst w ENC[...] przechodził jako szyfrogram."""
    fakes = [
        "ENC[sk-live-jawny-sekret]",
        f"ENC[AES256_GCM,data:jawny sekret!,iv:{IV},tag:{TAG},type:str]",
        f"ENC[AES256_GCM,data:3q2+7w==,iv:krotkie=,tag:{TAG},type:str]",
        f"ENC[AES256_GCM,data:3q2+7w==,iv:{IV},tag:{TAG},type:haslo]",
    ]
    for fake in fakes:
        assert sops_check.problems(f"token: {fake}\n{SOPS}") == ["jawna wartość: token"], fake


def test_fake_mac_and_missing_recipients_detected() -> None:
    no_mac = f"key: {ENC}\nsops:\n{AGE}  mac: ENC[udawany]\n"
    assert "podpisu mac" in sops_check.problems(no_mac)[0]
    no_age = f"key: {ENC}\nsops:\n  mac: {ENC}\n"
    assert "odbiorców age" in sops_check.problems(no_age)[0]


def test_invalid_yaml_detected() -> None:
    assert sops_check.problems("a: [b\n")[0].startswith("niepoprawny YAML")


def test_repo_secret_files_are_encrypted() -> None:
    files = sops_check.tracked_files()
    assert files, "w repozytorium powinien być co najmniej infra/secrets/local.enc.yaml"
    for path in files:
        assert sops_check.problems(path.read_text(encoding="utf-8")) == [], path


def test_main_returns_error_for_plaintext(tmp_path: Path) -> None:
    leak = tmp_path / "staging.enc.yaml"
    leak.write_text("db_password: hunter2\n", encoding="utf-8")
    assert sops_check.main(["sops_check.py", str(leak)]) == 1
