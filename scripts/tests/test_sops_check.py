"""Testy scripts/sops_check.py: jawny sekret w pliku *.enc.yaml musi zostać wykryty."""

from pathlib import Path

import sops_check

ENC = "ENC[AES256_GCM,data:abc=,iv:x=,tag:y=,type:str]"
SOPS = f"sops:\n  mac: {ENC}\n  version: 3.13.3\n"


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
