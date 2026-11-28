"""Cache odpowiedzi rynkowych w Valkey (roadmapa E6, punkt 3 ścieżki pracy; bramka G6p).

- **Co:** odpowiedzi 200 na GET endpointów rynkowych (`/v1/assets…`, `/v1/market/overview`),
  całe ciało JSON. Klucz: ścieżka i posortowane parametry zapytania.
- **TTL** dopasowany do interwału: do końca bieżącego okresu UTC (świece `1h`/`4h`/`1d`
  według parametru `timeframe`, pozostałe endpointy do końca bieżącej godziny), najwyżej
  doba; po tej chwili dane i tak mogą się zmienić (nowa świeca).
- **Unieważnianie po `candle.closed`:** każda instancja api czyta strumień `ev:candle.closed`
  przez `XREAD` (bez grupy konsumentów, więc każda dostaje każde zdarzenie; decyzja
  właściciela 28.11.2026) i podbija licznik wersji aktywa (`INCR`). Wersje (globalna
  i aktywa) są częścią klucza i są czytane **przed** zapytaniem do bazy, więc odpowiedź
  policzona przed zdarzeniem, a zapisana po nim, ląduje pod starą wersją i nie zostanie
  odczytana (bez wyścigu). Zdarzenie bez rozpoznawalnego aktywa podbija wersję globalną.
- **Brak Valkey nie daje nieaktualnych danych:** cache jest używany tylko wtedy, gdy
  słuchacz strumienia tej instancji jest zdrowy (ostatnie udane `XREAD` niedawno); po
  każdym (ponownym) połączeniu słuchacz podbija wersję globalną (mógł przegapić zdarzenia)
  i czyta tylko nowe zdarzenia. Błąd Valkey przy odczycie albo zapisie = odpowiedź prosto
  z bazy. Nagłówek `Cache-Status` (RFC 9211): `goatcash; hit`, `; fwd=miss` albo
  `; fwd=bypass`.
- Status DQ w przeglądzie zmienia się bez zdarzenia `candle.closed`; jego opóźnienie
  ogranicza TTL przeglądu (koniec bieżącej godziny).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from collections.abc import Callable
from typing import Any, Protocol, cast
from urllib.parse import parse_qsl
from uuid import UUID

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from goatcash.marketdata.api import CANDLE_STREAM, asset_public_id

log = logging.getLogger("goatcash.api.cache")
PREFIX = "api:v1"
GLOBAL = f"{PREFIX}:ver:all"
HOUR_S = 3600
OK = 200
PERIOD_S = {"1h": HOUR_S, "4h": 4 * HOUR_S, "1d": 24 * HOUR_S}
MAX_TTL_S = 24 * HOUR_S
BLOCK_MS = 5000  # XREAD BLOCK; słuchacz zdrowy, gdy ostatnie XREAD skończyło się niedawno
STALE_AFTER_S = 3 * BLOCK_MS / 1000
CACHED = re.compile(r"^/v1/(assets(/[0-9a-fA-F-]{36}(/candles)?)?|market/overview)$")
ASSET_IN_PATH = re.compile(r"^/v1/assets/([0-9a-fA-F-]{36})")


class Valkey(Protocol):
    """Część klienta redis-py używana przez cache (atrapa w testach ma te same metody)."""

    def get(self, name: str) -> Any: ...
    def mget(self, keys: list[str]) -> list[Any]: ...
    def set(self, name: str, value: bytes, ex: int) -> Any: ...
    def incr(self, name: str) -> Any: ...
    def xread(self, streams: dict[str, str], count: int, block: int) -> Any: ...
    def xrevrange(self, name: str, max: str, min: str, count: int) -> Any: ...


def ttl_seconds(path: str, query: list[tuple[str, str]], now: float) -> int:
    """Sekundy do końca bieżącego okresu interwału (co najmniej 1, najwyżej doba)."""
    timeframe = dict(query).get("timeframe", "")
    period = PERIOD_S.get(timeframe, HOUR_S) if path.endswith("/candles") else HOUR_S
    left = period - int(now) % period
    return max(1, min(left, MAX_TTL_S))


def asset_version_key(public_id: UUID | str) -> str:
    return f"{PREFIX}:ver:{str(public_id).lower()}"


def asset_from_event(fields: dict[Any, Any]) -> UUID | None:
    """Publiczny identyfikator aktywa bazowego z koperty `candle.closed` (None = nieznane)."""
    raw = fields.get("event", fields.get(b"event"))
    try:
        text = raw.decode() if isinstance(raw, bytes) else str(raw)
        symbol = str(json.loads(text)["payload"]["symbol"])
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    base = symbol.split("-", maxsplit=1)[0] if "-" in symbol else ""
    return asset_public_id(base.upper()) if re.fullmatch(r"[A-Za-z0-9]{2,15}", base) else None


class Invalidator:
    """Słuchacz `ev:candle.closed` (XREAD) jednej instancji api; podbija wersje w Valkey."""

    def __init__(self, client: Valkey, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._client = client
        self._clock = clock
        self._last_ok: float | None = None
        self._last_id: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def healthy(self) -> bool:
        last = self._last_ok
        return last is not None and self._clock() - last < STALE_AFTER_S

    def connect(self) -> None:
        """Start albo powrót po błędzie: mogły przepaść zdarzenia, więc wszystko nieważne."""
        self._last_ok = None
        newest = self._client.xrevrange(CANDLE_STREAM, max="+", min="-", count=1)
        self._last_id = _id(newest[0][0]) if newest else "0-0"
        self._client.incr(GLOBAL)
        self._last_ok = self._clock()

    def poll(self, block_ms: int = BLOCK_MS) -> int:
        """Jedno XREAD; zwraca liczbę zdarzeń. Wyjątek Valkey = słuchacz niezdrowy."""
        try:
            if self._last_id is None:
                self.connect()
            reply = cast(
                list[tuple[Any, list[tuple[Any, dict[Any, Any]]]]] | None,
                self._client.xread({CANDLE_STREAM: str(self._last_id)}, count=500, block=block_ms),
            )
            handled = 0
            for _stream, entries in reply or []:
                for entry_id, fields in entries:
                    asset = asset_from_event(fields)
                    self._client.incr(GLOBAL if asset is None else asset_version_key(asset))
                    self._last_id = _id(entry_id)
                    handled += 1
        except Exception:
            # Stan nieznany (mogło przepaść zdarzenie): cache wyłączony do ponownego connect().
            self._last_ok = None
            self._last_id = None
            raise
        self._last_ok = self._clock()
        return handled

    def run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                self.poll()
                backoff = 1.0
            except Exception as exc:
                log.warning("słuchacz candle.closed: %s; cache wyłączony", type(exc).__name__)
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 30.0)

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run, name="cache-invalidator", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


def _id(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


class ResponseCache:
    """Middleware ASGI cache odpowiedzi 200 dla GET endpointów rynkowych."""

    def __init__(
        self,
        app: ASGIApp,
        client: Valkey | None,
        invalidator: Invalidator | None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.app = app
        self._client = client
        self._invalidator = invalidator
        self._now = now

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or scope.get("method") != "GET" or not CACHED.match(path):
            await self.app(scope, receive, send)
            return
        client, inv = self._client, self._invalidator
        if client is None or inv is None or not inv.healthy():
            await self._forward(scope, receive, send, "bypass")
            return
        query = _query(scope)
        try:
            key = self._key(client, path, query)
            hit = client.get(key)
        except Exception as exc:
            log.warning("cache: odczyt nieudany (%s)", type(exc).__name__)
            await self._forward(scope, receive, send, "bypass")
            return
        if hit is not None:
            await _send_cached(send, hit if isinstance(hit, bytes) else str(hit).encode())
            return
        body = await self._forward(scope, receive, send, "miss")
        if body is not None:
            try:
                client.set(key, body, ex=ttl_seconds(path, query, self._now()))
            except Exception as exc:
                log.warning("cache: zapis nieudany (%s)", type(exc).__name__)

    @staticmethod
    def _key(client: Valkey, path: str, query: list[tuple[str, str]]) -> str:
        match = ASSET_IN_PATH.match(path)
        asset_key = asset_version_key(match.group(1)) if match else f"{PREFIX}:ver:none"
        versions = [_id(v) if v is not None else "0" for v in client.mget([GLOBAL, asset_key])]
        # Wszystkie pary (także powtórzone parametry), posortowane: inne zapytanie = inny klucz.
        canonical = json.dumps([path, sorted(query)], separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        return f"{PREFIX}:resp:{versions[0]}:{versions[1]}:{digest}"

    async def _forward(
        self, scope: Scope, receive: Receive, send: Send, state: str
    ) -> bytes | None:
        """Przekazuje zapytanie do aplikacji; zwraca ciało odpowiedzi 200 JSON (do zapisu)."""
        state_box: dict[str, int | bool] = {"status": 0, "json": False}
        chunks: list[bytes] = []

        async def capture(message: Message) -> None:
            if message["type"] == "http.response.start":
                state_box["status"] = int(message["status"])
                headers = list(message.get("headers", []))
                state_box["json"] = any(
                    k.lower() == b"content-type" and v == b"application/json" for k, v in headers
                )
                headers.append((b"cache-status", f"goatcash; fwd={state}".encode()))
                message["headers"] = headers
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
            await send(message)

        await self.app(scope, receive, capture)
        return (
            b"".join(chunks)
            if state == "miss" and state_box["status"] == OK and state_box["json"]
            else None
        )


def _query(scope: Scope) -> list[tuple[str, str]]:
    raw = scope.get("query_string", b"").decode("latin-1")
    return parse_qsl(raw, keep_blank_values=True)


async def _send_cached(send: Send, body: bytes) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"cache-status", b"goatcash; hit"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
