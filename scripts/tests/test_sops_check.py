"""Testy scripts/sops_check.py na prawdziwym wyniku `sops -e` i jego zmodyfikowanych wersjach.

fixtures/sops_real.yaml to wynik `sops -e --age` (sops 3.13.3) dla pliku z kluczem
DATABASE_URL, pustą wartością, null, listą z komentarzem, pustą mapą, liczbą, komentarzem
w osobnym wierszu i komentarzami po wartości (w mapie i w liście map).
Klucz prywatny użyty do zaszyfrowania został od razu skasowany.
"""

import base64
from pathlib import Path

import pytest
import sops_check
import yaml

REAL = (Path(__file__).parent / "fixtures" / "sops_real.yaml").read_text(encoding="utf-8")
IV = "e9KIjXG2YeRmNKQbjb78v1eBzwrUd03g+C0ofz2Bloo="  # 32 bajty
TAG = "m/ysnGowjbuQteXRAwDX+g=="  # 16 bajtów
ENC = f"ENC[AES256_GCM,data:3q2+7w==,iv:{IV},tag:{TAG},type:str]"
CMT = f"ENC[AES256_GCM,data:3q2+7w==,iv:{IV},tag:{TAG},type:comment]"
LEAK = "AKIAIOSFODNN7EXAMPLE"


def with_line(extra: str) -> str:
    """Wstawia wiersz na początek prawdziwego pliku (przed blok sops)."""
    return extra + "\n" + REAL


def test_real_sops_output_passes() -> None:
    assert sops_check.problems(REAL) == []


def test_repo_secret_files_are_encrypted() -> None:
    files = sops_check.tracked_files()
    assert any(p.name == "local.enc.yaml" for p in files)
    for path in files:
        assert sops_check.problems(path.read_text(encoding="utf-8")) == [], path


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ("token: jawny-sekret", "jawna wartość: token"),
        ("port: 5432", "jawna wartość: port"),
        ("token: ENC[sk-live-jawny-sekret]", "jawna wartość: token"),
        (
            f"token: ENC[AES256_GCM,data:jawny sekret!,iv:{IV},tag:{TAG},type:str]",
            "jawna wartość: token",
        ),
        (
            f"token: ENC[AES256_GCM,data:3q2+7w==,iv:krotkie=,tag:{TAG},type:str]",
            "jawna wartość: token",
        ),
        (
            f"token: ENC[AES256_GCM,data:3q2+7w==,iv:{IV},tag:{TAG},type:haslo]",
            "jawna wartość: token",
        ),
        (f"token: {CMT}", "jawna wartość: token"),
        (f"password_unencrypted: {ENC}", "klucz z sufiksem _unencrypted"),
        (f'"klucz ze spacją": {ENC}', "klucz nie jest identyfikatorem"),
        (f"# {LEAK}", "jawny komentarz albo znak # w wierszu 1"),
        (f"token: {ENC} # jawne", "jawny komentarz albo znak # w wierszu 1"),
        (f"db: &{LEAK} {ENC}", "kotwica YAML w wierszu 1"),
        (f"db: !!str {ENC}", "tag YAML w wierszu 1"),
    ],
)
def test_plaintext_in_content_detected(extra: str, expected: str) -> None:
    found = sops_check.problems(with_line(extra))
    assert any(expected in p for p in found), found


def test_alias_and_directive_detected() -> None:
    alias = REAL.replace("obj: {}", f"base: &a {ENC}\nobj: *a")
    found = sops_check.problems(alias)
    assert any("alias YAML" in p for p in found), found
    directive = f"%TAG !x! tag:{LEAK},2026:\n---\n" + REAL
    assert any("dyrektywa YAML" in p for p in sops_check.problems(directive))


def test_duplicate_key_detected() -> None:
    first_key = REAL.splitlines()[0].split(":")[0]
    found = sops_check.problems(f'{first_key}: "{LEAK}"\n' + REAL)
    assert any("zduplikowany klucz" in p for p in found), found


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("    version: 3.13.3", f"    version: {LEAK}", "sops.version"),
        (
            "    lastmodified: ",
            f'    lastmodified: "{LEAK}"\n    x_lastmodified: ',
            "nieznane pole",
        ),
        (
            "    unencrypted_suffix: _unencrypted",
            "    unencrypted_suffix: _jawne",
            "unencrypted_suffix",
        ),
        ("    mac: ENC[", "    mac: ENC[udawany", "podpisu mac"),
        (
            "          recipient: age1",
            f"          note: {LEAK}\n          recipient: age1",
            "recipient i enc",
        ),
        ("          recipient: age1", "          recipient: AKIA1", "kluczem publicznym age"),
    ],
)
def test_sops_block_tampering_detected(old: str, new: str, expected: str) -> None:
    assert old in REAL
    found = sops_check.problems(REAL.replace(old, new, 1))
    assert any(expected in p for p in found), found


def test_extra_sops_field_detected() -> None:
    found = sops_check.problems(REAL.replace("    version:", f"    notatka: {LEAK}\n    version:"))
    assert "nieznane pole w bloku sops: notatka" in found


def test_file_without_sops_block_and_invalid_yaml() -> None:
    assert "nie jest zaszyfrowany" in sops_check.problems("api_key: sk-123\n")[0]
    assert sops_check.problems("a: [b\n")[0].startswith("niepoprawny YAML")


def test_main_returns_error_for_plaintext(tmp_path: Path) -> None:
    leak = tmp_path / "staging.enc.yaml"
    leak.write_text("db_password: hunter2\n", encoding="utf-8")
    assert sops_check.main(["sops_check.py", str(leak)]) == 1
    ok = tmp_path / "local.enc.yaml"
    ok.write_text(REAL, encoding="utf-8")
    assert sops_check.main(["sops_check.py", str(ok)]) == 0


def test_fake_age_armor_detected() -> None:
    """Uwaga z niezależnego przeglądu: pancerz age z base64 jawnego tekstu przechodził."""
    fake = base64.b64encode(b"haslo: hunter2\n" * 4).decode()
    lines = [fake[i : i + 64] for i in range(0, len(fake), 64)]
    body = "".join(f"            {line}\n" for line in lines)
    start = REAL.index("-----BEGIN AGE ENCRYPTED FILE-----\n") + len(
        "-----BEGIN AGE ENCRYPTED FILE-----\n"
    )
    end = REAL.index("            -----END AGE ENCRYPTED FILE-----")
    forged = REAL[:start] + body + REAL[end:]
    meta = yaml.safe_load(forged)["sops"]["age"][0]["enc"]
    assert sops_check.AGE_ARMOR_RE.fullmatch(meta), "fałszywka musi mieć poprawną budowę pancerza"
    assert not sops_check.is_age_armor(meta)
    assert "sops.age[0].enc nie jest zaszyfrowanym blokiem age" in sops_check.problems(forged)
