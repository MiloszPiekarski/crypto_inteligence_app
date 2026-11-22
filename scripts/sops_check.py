"""Sprawdza, że każdy plik *.enc.yaml w repozytorium jest naprawdę zaszyfrowany przez SOPS.

Dwie warstwy ochrony plików z sekretami:
- gitleaks skanuje je jak każdy inny plik (bez wyjątków), więc sekret o rozpoznawalnym
  kształcie (klucz AWS, token GitHub itd.) zostanie wykryty wszędzie: w wartości, nazwie
  klucza, komentarzu czy metadanych;
- ten skrypt pilnuje budowy pliku, czyli tego, czego gitleaks nie widzi (np. jawne hasło
  o niskiej entropii): plik musi wyglądać dokładnie tak, jak wynik `sops -e`.

Plik przechodzi, gdy:
- każda wartość to szyfrogram SOPS o poprawnej budowie (AES256_GCM, dane w base64, iv 32 B,
  tag 16 B, typ danych) albo wartość, której SOPS nie szyfruje: "", null, {} lub [],
- typ `comment` występuje tylko w komentarzu (`#ENC[...]` w osobnym wierszu albo po wartości,
  albo element listy), a każdy `#` w pliku zaczyna zaszyfrowany komentarz,
- nazwy kluczy to identyfikatory (litery, cyfry, `_`, `.`, `-`, do 64 znaków),
- nie ma zduplikowanych kluczy, kotwic, aliasów, tagów ani dyrektyw YAML,
- blok `sops` ma dokładnie pola zapisywane przez `sops -e` z kluczem age, w poprawnym formacie
  (pancerz age po zdekodowaniu zaczyna się nagłówkiem `age-encryption.org/v1`).

Nazwy kluczy ze spacją są odrzucane (SOPS je dopuszcza, ale w projekcie ich nie używamy).

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
KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}")
AGE_RECIPIENT_RE = re.compile(r"age1[02-9ac-hj-np-z]{58}")
AGE_ARMOR_RE = re.compile(
    r"-----BEGIN AGE ENCRYPTED FILE-----\n"
    r"(?:[A-Za-z0-9+/=]{1,64}\n)+"
    r"-----END AGE ENCRYPTED FILE-----\n?"
)
AGE_HEADER = b"age-encryption.org/v1\n"
LASTMODIFIED_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
SOPS_REQUIRED = frozenset({"age", "lastmodified", "mac", "version"})
SOPS_ALLOWED = SOPS_REQUIRED | {"unencrypted_suffix"}
UNENCRYPTED_SUFFIX = "_unencrypted"


class _NoDuplicatesLoader(yaml.SafeLoader):
    """SafeLoader, który odrzuca zduplikowane klucze zamiast brać ostatni."""


def _construct_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict[object, object]:
    seen: set[object] = set()
    for key_node, _ in node.value:
        key = cast(object, loader.construct_object(key_node))  # pyright: ignore[reportUnknownMemberType]
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"zduplikowany klucz: {key}", key_node.start_mark
            )
        seen.add(key)
    return cast(dict[object, object], loader.construct_mapping(node))


_NoDuplicatesLoader.add_constructor(  # pyright: ignore[reportUnknownMemberType]
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def _b64len(value: str) -> int | None:
    try:
        return len(base64.b64decode(value, validate=True))
    except (binascii.Error, ValueError):
        return None


def is_sops_ciphertext(value: str, *, comment: bool = False) -> bool:
    """True tylko dla szyfrogramu SOPS o poprawnej budowie (nie dla ENC[tekst jawny]).

    Typ `comment` jest dozwolony wyłącznie dla komentarza, a dla wartości jest odrzucany.
    """
    match = ENC_RE.fullmatch(value)
    if match is None or (match["type"] == "comment") != comment:
        return False
    return (
        _b64len(match["data"]) is not None
        and _b64len(match["iv"]) == IV_BYTES
        and _b64len(match["tag"]) == TAG_BYTES
    )


def is_age_armor(value: str) -> bool:
    """Pancerz age o poprawnej budowie, którego treść zaczyna się nagłówkiem formatu age
    (a nie np. zakodowanym w base64 jawnym tekstem)."""
    if not AGE_ARMOR_RE.fullmatch(value):
        return False
    body = "".join(value.strip().splitlines()[1:-1])
    try:
        return base64.b64decode(body, validate=True).startswith(AGE_HEADER)
    except (binascii.Error, ValueError):
        return False


def syntax_problems(text: str) -> list[str]:
    """Kotwice, aliasy, tagi i dyrektywy YAML mogą nieść jawny tekst; SOPS ich nie zapisuje."""
    found: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.startswith("%"):
            found.append(f"dyrektywa YAML w wierszu {line_no}")
    parsed = cast(object, yaml.parse(text, Loader=yaml.SafeLoader))  # pyright: ignore[reportUnknownMemberType]
    events = list(cast("list[yaml.Event]", parsed))
    for event in events:
        line_no = cast(int, event.start_mark.line) + 1  # pyright: ignore[reportUnknownMemberType]
        if isinstance(event, yaml.AliasEvent):
            found.append(f"alias YAML w wierszu {line_no}")
        elif isinstance(event, yaml.NodeEvent) and event.anchor is not None:
            found.append(f"kotwica YAML w wierszu {line_no}")
        if (
            isinstance(event, yaml.ScalarEvent | yaml.CollectionStartEvent)
            and event.tag is not None
        ):
            found.append(f"tag YAML w wierszu {line_no}")
    return found


def comment_problems(text: str) -> list[str]:
    """Każdy `#` w pliku musi zaczynać zaszyfrowany komentarz SOPS: w osobnym wierszu
    (`#ENC[...]`) albo na końcu wiersza po wartości (`klucz: ENC[...] #ENC[...]`)."""
    found: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if "#" not in line:
            continue
        before, _, comment = line.partition("#")
        ok = (
            line.count("#") == 1
            and (not before.strip() or before.endswith(" "))
            and is_sops_ciphertext(comment.strip(), comment=True)
        )
        if not ok:
            found.append(f"jawny komentarz albo znak # w wierszu {line_no}")
    return found


def _is_unencrypted_leaf(node: object) -> bool:
    """Wartości, których `sops -e` nie szyfruje: pusty tekst, null, pusta mapa i lista."""
    if isinstance(node, dict | list):
        return not node
    return node is None or node == ""


def plaintext_paths(node: object, prefix: str = "") -> list[str]:
    """Zwraca opisy miejsc, w których jest jawny tekst (wartość albo nazwa klucza)."""
    if isinstance(node, dict) and node:
        found: list[str] = []
        for key, value in cast(dict[object, object], node).items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if not (isinstance(key, str) and KEY_RE.fullmatch(key)):
                found.append(f"klucz nie jest identyfikatorem: {path}")
            elif key.endswith(UNENCRYPTED_SUFFIX):
                found.append(
                    f"klucz z sufiksem {UNENCRYPTED_SUFFIX} (SOPS go nie szyfruje): {path}"
                )
            found += plaintext_paths(value, path)
        return found
    if isinstance(node, list) and node:
        found = []
        for i, value in enumerate(cast(list[object], node)):
            if isinstance(value, str) and is_sops_ciphertext(value, comment=True):
                continue  # komentarz wewnątrz listy, zapisany przez SOPS jako element
            found += plaintext_paths(value, f"{prefix}[{i}]")
        return found
    if _is_unencrypted_leaf(cast(object, node)) or (
        isinstance(node, str) and is_sops_ciphertext(node)
    ):
        return []
    return [f"jawna wartość: {prefix or '<root>'}"]


def sops_block_problems(meta: dict[str, object]) -> list[str]:
    """Blok `sops` musi mieć dokładnie budowę zapisywaną przez `sops -e` z kluczem age."""
    found = [f"nieznane pole w bloku sops: {k}" for k in meta if k not in SOPS_ALLOWED]
    found += [f"brak pola w bloku sops: {k}" for k in sorted(SOPS_REQUIRED - meta.keys())]
    if not is_sops_ciphertext(str(meta.get("mac", ""))):
        found.append("brak poprawnego podpisu mac w bloku sops")
    if not LASTMODIFIED_RE.fullmatch(str(meta.get("lastmodified", ""))):
        found.append("sops.lastmodified nie jest datą ISO (UTC)")
    if not VERSION_RE.fullmatch(str(meta.get("version", ""))):
        found.append("sops.version nie jest numerem wersji")
    if "unencrypted_suffix" in meta and meta["unencrypted_suffix"] != UNENCRYPTED_SUFFIX:
        found.append(f"sops.unencrypted_suffix inny niż domyślny {UNENCRYPTED_SUFFIX}")
    recipients = meta.get("age")
    if not isinstance(recipients, list) or not recipients:
        return [*found, "blok sops nie ma odbiorców age"]
    for i, item in enumerate(cast(list[object], recipients)):
        entry = cast(dict[str, object], item) if isinstance(item, dict) else {}
        if set(entry) != {"recipient", "enc"}:
            found.append(f"sops.age[{i}] musi mieć dokładnie pola recipient i enc")
            continue
        if not AGE_RECIPIENT_RE.fullmatch(str(entry["recipient"])):
            found.append(f"sops.age[{i}].recipient nie jest kluczem publicznym age")
        if not is_age_armor(str(entry["enc"])):
            found.append(f"sops.age[{i}].enc nie jest zaszyfrowanym blokiem age")
    return found


def problems(text: str) -> list[str]:
    try:
        data = cast(object, yaml.load(text, Loader=_NoDuplicatesLoader))  # noqa: S506 - SafeLoader
        syntax = syntax_problems(text)
    except yaml.YAMLError as exc:
        return [f"niepoprawny YAML: {exc}"]
    if not isinstance(data, dict):
        return ["brak mapy YAML z blokiem sops"]
    doc = cast(dict[str, object], data)
    meta = doc.get("sops")
    if not isinstance(meta, dict):
        return ["brak bloku sops (plik nie jest zaszyfrowany przez SOPS)"]
    found = syntax + sops_block_problems(cast(dict[str, object], meta))
    found += comment_problems(text)
    content = {k: v for k, v in doc.items() if k != "sops"}
    return found + plaintext_paths(content)


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
