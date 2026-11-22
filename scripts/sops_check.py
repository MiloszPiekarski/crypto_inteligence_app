"""Sprawdza, że każdy plik *.enc.yaml w repozytorium jest naprawdę zaszyfrowany przez SOPS.

gitleaks pomija pliki infra/secrets/*.enc.yaml (zawierają tylko szyfrogramy), więc bez tej
kontroli jawny sekret w pliku nazwanym *.enc.yaml przeszedłby niezauważony. Plik jest
poprawny, gdy ma blok `sops` z `mac`, a każda wartość poza nim ma postać ENC[...].

Użycie: python scripts/sops_check.py [PLIK ...]   (bez argumentów: pliki śledzone przez git)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).resolve().parent.parent


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
    if isinstance(node, str) and node.startswith("ENC[") and node.endswith("]"):
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
    if not isinstance(meta, dict) or not str(
        cast(dict[str, object], meta).get("mac", "")
    ).startswith("ENC["):
        return ["brak bloku sops z podpisem mac (plik nie jest zaszyfrowany przez SOPS)"]
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
