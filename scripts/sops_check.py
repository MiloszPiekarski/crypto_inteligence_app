"""Sprawdza, że każdy plik *.enc.yaml w repozytorium jest naprawdę zaszyfrowany przez SOPS.

gitleaks pomija pliki infra/secrets/*.enc.yaml (zawierają tylko szyfrogramy), więc bez tej
kontroli jawny sekret w pliku nazwanym *.enc.yaml przeszedłby niezauważony. Plik jest
poprawny, gdy ma blok `sops` z `mac` i odbiorcami age, a każda wartość poza nim jest
szyfrogramem SOPS o poprawnej budowie: AES256_GCM, dane w base64, iv 32 bajty, tag
16 bajtów, znany typ. Tekst jawny „opakowany” w ENC[...] jest odrzucany.

Ograniczenie (zapisane w docs/gates/G1.md): bez klucza prywatnego nie da się sprawdzić
podpisu MAC, więc celowo spreparowany szyfrogram o poprawnej budowie przejdzie tę kontrolę.
MAC sprawdza `sops -d` przy odszyfrowaniu (lokalnie w bramce G1 dla local.enc.yaml).

Użycie: python scripts/sops_check.py [PLIK ...]   (bez argumentów: pliki śledzone przez git)
"""

from __future__ import annotations

import base64
import binascii
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).resolve().parent.parent

ENC_RE = re.compile(
    r"ENC\[AES256_GCM,data:(?P<data>[A-Za-z0-9+/]*={0,2}),"
    r"iv:(?P<iv>[A-Za-z0-9+/]+={0,2}),tag:(?P<tag>[A-Za-z0-9+/]+={0,2}),"
    r"type:(?P<type>str|int|float|bool|bytes|comment)\]"
)
IV_BYTES = 32
TAG_BYTES = 16


def _b64len(value: str) -> int | None:
    try:
        return len(base64.b64decode(value, validate=True))
    except (binascii.Error, ValueError):
        return None


def is_sops_ciphertext(value: str) -> bool:
    """True tylko dla szyfrogramu SOPS o poprawnej budowie (nie dla ENC[tekst jawny])."""
    match = ENC_RE.fullmatch(value)
    if match is None:
        return False
    return (
        _b64len(match["data"]) is not None
        and _b64len(match["iv"]) == IV_BYTES
        and _b64len(match["tag"]) == TAG_BYTES
    )


def plaintext_paths(node: object, prefix: str = "") -> list[str]:
    """Zwraca ścieżki wartości, które NIE są szyfrogramem SOPS."""
    if isinstance(node, dict):
        found: list[str] = []
        for key, value in cast(dict[object, object], node).items():
            found += plaintext_paths(value, f"{prefix}.{key}" if prefix else str(key))
        return found
    if isinstance(node, list):
        found = []
        for i, value in enumerate(cast(list[object], node)):
            found += plaintext_paths(value, f"{prefix}[{i}]")
        return found
    if isinstance(node, str) and is_sops_ciphertext(node):
        return []
    return [prefix or "<root>"]


def problems(text: str) -> list[str]:
    try:
        data = cast(object, yaml.safe_load(text))
    except yaml.YAMLError as exc:
        return [f"niepoprawny YAML: {exc}"]
    if not isinstance(data, dict):
        return ["brak mapy YAML z blokiem sops"]
    doc = cast(dict[str, object], data)
    meta = doc.get("sops")
    if not isinstance(meta, dict):
        return ["brak bloku sops (plik nie jest zaszyfrowany przez SOPS)"]
    sops_meta = cast(dict[str, object], meta)
    if not is_sops_ciphertext(str(sops_meta.get("mac", ""))):
        return ["brak poprawnego podpisu mac w bloku sops (plik nie jest zaszyfrowany przez SOPS)"]
    recipients = sops_meta.get("age")
    if not isinstance(recipients, list) or not recipients:
        return ["blok sops nie ma odbiorców age"]
    content = {k: v for k, v in doc.items() if k != "sops"}
    return [f"jawna wartość: {p}" for p in plaintext_paths(content)]


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.enc.yaml"],  # noqa: S607 - git z PATH, jak w Makefile
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [ROOT / line for line in out.splitlines() if line]


def main(argv: list[str]) -> int:
    files = [Path(a) for a in argv[1:]] or tracked_files()
    bad = 0
    for path in files:
        found = problems(path.read_text(encoding="utf-8"))
        for problem in found:
            print(f"{path}: {problem}")
        bad += bool(found)
    print(f"Pliki *.enc.yaml: {len(files)}, niezaszyfrowane: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
