"""Kursor paginacji: nieprzezroczysty dla klienta (base64url), związany z zasobem.

Treść: `<rodzaj>|<zakres>|<klucz>`, np. `assets||ETH` albo `candles|<uuid>:4h|1700000000000`.
Kursor z innego zasobu (inne aktywo, inny interwał) albo uszkodzony daje 400 (RFC 9457),
a nie cichą pustą stronę. Kursor nie jest podpisany: zmieniony ręcznie przesuwa tylko
pozycję w danych publicznych, więc nie daje żadnego dostępu.
"""

from __future__ import annotations

import base64
import binascii
import re

from fastapi import HTTPException

MAX_LEN = 200
_SYMBOL = re.compile(r"[A-Z0-9]{2,15}")
# Do 13 cyfr ms (rok 2286): dłuższy znacznik przekracza zakres datetime (500 zamiast 400).
_TS = re.compile(r"[0-9]{1,13}")


def encode(kind: str, scope: str, key: str) -> str:
    raw = f"{kind}|{scope}|{key}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(kind: str, scope: str, cursor: str) -> str:
    bad = HTTPException(status_code=400, detail="Niepoprawny kursor paginacji.")
    if len(cursor) > MAX_LEN or not re.fullmatch(r"[A-Za-z0-9_-]+", cursor):
        raise bad
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise bad from None
    parts = raw.split("|")
    if len(parts) != 3 or parts[0] != kind or parts[1] != scope:  # noqa: PLR2004
        raise bad
    return parts[2]


def decode_symbol(cursor: str) -> str:
    key = _decode("assets", "", cursor)
    if not _SYMBOL.fullmatch(key):
        raise HTTPException(status_code=400, detail="Niepoprawny kursor paginacji.")
    return key


def decode_ts(scope: str, cursor: str) -> int:
    key = _decode("candles", scope, cursor)
    if not _TS.fullmatch(key):
        raise HTTPException(status_code=400, detail="Niepoprawny kursor paginacji.")
    return int(key)
