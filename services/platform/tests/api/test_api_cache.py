"""Cache odpowiedzi w Valkey (E6, punkt 3 ścieżki pracy; bramka G6p, `api-cache`).

Atrapa Valkey o semantyce poleceń używanych przez cache (GET/SET EX/MGET/INCR, XADD,
XREAD, XREVRANGE; awaria = ConnectionError), więc logika jest sprawdzana bez Dockera;
integrację z prawdziwym Valkey sprawdza `test_api_cache_valkey.py` (`make api-db-test`).

- trafienie: druga odpowiedź z cache, bez zapytania do bazy, identyczna treść;
- `candle.closed` (XREAD) unieważnia tylko odpowiedzi tego aktywa; zdarzenie bez
  rozpoznawalnego aktywa unieważnia wszystko;
- wyścig: odpowiedź policzona przed zdarzeniem, a zapisana po nim, nie jest serwowana;
- brak Valkey, awaria w trakcie i niezdrowy słuchacz: odpowiedzi prosto z bazy (aktualne),
  bez błędów; po ponownym połączeniu wpisy sprzed przerwy są nieważne;
- TTL do końca bieżącego okresu interwału; błędy (4xx) nie trafiają do cache;
- odpowiedź z cache ma nagłówki bezpieczeństwa i CORS; Schemathesis z włączonym cache.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast
from uuid import UUID

import pytest
from api_data import NAMES, QUOTE, conformance_schema, refs, validate
from fastapi.testclient import TestClient
from httpx import Response
from hypothesis import HealthCheck, settings
from redis.exceptions import ConnectionError as ValkeyDown

from goatcash.http_api import cache
from goatcash.http_api.app import create_app
from goatcash.http_api.security import APP_ORIGIN
from goatcash.marketdata.api import (
    CANDLE_STREAM,
    HOUR_MS,
    InMemoryReader,
    RefCandle,
    asset_public_id,
)

BTC = asset_public_id("BTC")
ETH = asset_public_id("ETH")


class FakeValkey:
    """Atrapa części Valkey używanej przez cache (czas wygaśnięcia z zegara testu)."""

    def __init__(self, now: Callable[[], float]) -> None:
        self.now = now
        self.data: dict[str, tuple[bytes, float | None]] = {}
        self.stream: list[tuple[str, dict[str, str]]] = []
        self.down = False
        self.ttls: dict[str, int] = {}

    def _check(self) -> None:
        if self.down:
            raise ValkeyDown("Valkey niedostępny")

    def _live(self, key: str) -> bytes | None:
        item = self.data.get(key)
        if item is None or (item[1] is not None and item[1] <= self.now()):
            self.data.pop(key, None)
            return None
        return item[0]

    def get(self, name: str) -> Any:
        self._check()
        return self._live(name)

    def mget(self, keys: list[str]) -> list[Any]:
        self._check()
        return [self._live(k) for k in keys]

    def set(self, name: str, value: bytes, ex: int) -> Any:
        self._check()
        self.data[name] = (value, self.now() + ex)
        self.ttls[name] = ex
        return True

    def incr(self, name: str) -> Any:
        self._check()
        value = int(self._live(name) or b"0") + 1
        self.data[name] = (str(value).encode(), None)
        return value

    def xadd(self, symbol: str) -> None:
        envelope = {"type": "candle.closed", "payload": {"symbol": symbol}}
        self.stream.append((f"{len(self.stream) + 1}-0", {"event": json.dumps(envelope)}))

    def xread(self, streams: dict[str, str], count: int, block: int) -> Any:
        self._check()
        last = int(streams[CANDLE_STREAM].split("-")[0])
        new = [(i, f) for i, f in self.stream if int(i.split("-")[0]) > last][:count]
        return [(CANDLE_STREAM, new)] if new else []

    def xrevrange(self, name: str, max: str, min: str, count: int) -> Any:
        self._check()
        return list(reversed(self.stream))[:count]


class Clock:
    def __init__(self) -> None:
        self.t = 1_767_225_600.0 + 600  # 2026-01-01 00:10 UTC

    def __call__(self) -> float:
        return self.t


class CountingReader:
    """Czytnik w pamięci z licznikiem zapytań i podmienialnymi danymi (nowa świeca)."""

    def __init__(self) -> None:
        self.calls = 0
        self.extra: list[RefCandle] = []
        self.during: Callable[[], None] | None = None
        self._inner = InMemoryReader(QUOTE, NAMES, refs())

    def add_candle(self, base: str) -> None:
        last = max(
            (r for r in refs() + self.extra if r.base == base and r.quote == QUOTE),
            key=lambda r: r.ts_ms,
        )
        self.extra.append(
            RefCandle(
                base,
                QUOTE,
                "1h",
                last.ts_ms + HOUR_MS,
                last.close,
                last.close,
                last.close,
                last.close,
                last.volume,
                last.sources,
                "median",
            )
        )
        self._inner = InMemoryReader(QUOTE, NAMES, refs() + self.extra)

    def _hit(self) -> InMemoryReader:
        self.calls += 1
        inner = self._inner
        if self.during is not None:  # zdarzenie w trakcie liczenia odpowiedzi (wyścig)
            hook, self.during = self.during, None
            hook()
        return inner

    def list_assets(self, after: str | None, limit: int) -> Any:
        return self._hit().list_assets(after, limit)

    def get_asset(self, public_id: UUID) -> Any:
        return self._inner.get_asset(public_id)

    def candles(self, public_id: UUID, timeframe: Any, before_ms: int | None, limit: int) -> Any:
        return self._hit().candles(public_id, timeframe, before_ms, limit)

    def overview(self) -> Any:
        return self._hit().overview()


class Env:
    def __init__(self) -> None:
        self.clock = Clock()
        self.mono = Clock()
        self.valkey = FakeValkey(self.clock)
        self.inv = cache.Invalidator(cast(cache.Valkey, self.valkey), clock=self.mono)
        self.reader = CountingReader()
        app = create_app(self.reader, valkey=cast(cache.Valkey, self.valkey), invalidator=self.inv)
        # zegar TTL testu zamiast time.time
        for mw in app.user_middleware:
            if mw.cls is cache.ResponseCache:
                mw.kwargs["now"] = self.clock
        self.client = TestClient(app)
        self.inv.connect()

    def get(self, url: str, **kwargs: Any) -> Response:
        return cast(Response, self.client.get(url, **kwargs))  # pyright: ignore[reportUnknownMemberType]

    def candles(self, asset: UUID = BTC, timeframe: str = "1h") -> Response:
        return self.get(f"/v1/assets/{asset}/candles", params={"timeframe": timeframe, "limit": 3})


@pytest.fixture
def env() -> Env:
    return Env()


def state(response: Response) -> str:
    return response.headers["cache-status"]


def test_hit_serves_identical_body_without_database(env: Env) -> None:
    first = env.candles()
    assert state(first) == "goatcash; fwd=miss"
    calls = env.reader.calls
    second = env.candles()
    assert state(second) == "goatcash; hit"
    assert second.content == first.content
    assert env.reader.calls == calls


def test_candle_closed_invalidates_only_that_asset(env: Env) -> None:
    env.candles(BTC)
    env.candles(ETH)
    env.reader.add_candle("BTC")
    env.valkey.xadd("BTC-USDT")
    assert env.inv.poll(block_ms=0) == 1
    fresh = env.candles(BTC)
    assert state(fresh) == "goatcash; fwd=miss"
    assert fresh.json()["items"][0]["close"] == env.reader.candles(BTC, "1h", None, 1)[
        0
    ].close.__format__("f")
    assert state(env.candles(ETH)) == "goatcash; hit"


def test_overview_and_list_follow_global_events(env: Env) -> None:
    env.get("/v1/market/overview")
    assert state(env.get("/v1/market/overview")) == "goatcash; hit"
    env.valkey.xadd("niewiadomo")  # zdarzenie bez rozpoznawalnego aktywa: wszystko nieważne
    env.inv.poll(block_ms=0)
    assert state(env.get("/v1/market/overview")) == "goatcash; fwd=miss"
    assert state(env.candles()) == "goatcash; fwd=miss"


def test_overview_ttl_ends_with_current_hour(env: Env) -> None:
    """Przegląd zależy od wszystkich aktywów: zdarzenie aktywa go nie unieważnia, ale TTL
    kończy się z końcem bieżącej godziny (zapisany jawnie w module, tu sprawdzony)."""
    env.get("/v1/market/overview")
    key = next(k for k in env.valkey.ttls if ":resp:" in k)
    assert env.valkey.ttls[key] == 3600 - 600


def test_race_response_computed_before_event_is_never_served(env: Env) -> None:
    def event_arrives() -> None:
        env.reader.add_candle("BTC")
        env.valkey.xadd("BTC-USDT")
        env.inv.poll(block_ms=0)

    env.reader.during = event_arrives
    stale = env.candles()  # policzona ze starych danych, zapisana po zdarzeniu
    fresh = env.candles()
    assert state(fresh) == "goatcash; fwd=miss"
    assert fresh.content != stale.content


@pytest.mark.parametrize(
    ("timeframe", "ttl"), [("1h", 3000), ("4h", 4 * 3600 - 600), ("1d", 86400 - 600)]
)
def test_ttl_until_end_of_current_period(env: Env, timeframe: str, ttl: int) -> None:
    env.candles(timeframe=timeframe)
    (key,) = [k for k in env.valkey.ttls if ":resp:" in k]
    assert env.valkey.ttls[key] == ttl
    env.clock.t += ttl  # koniec okresu: wpis wygasa
    env.mono.t += 1
    assert state(env.candles(timeframe=timeframe)) == "goatcash; fwd=miss"


def test_ttl_function_bounds() -> None:
    assert cache.ttl_seconds("/v1/assets/x/candles", [("timeframe", "1h")], 3599.0) == 1
    assert cache.ttl_seconds("/v1/assets/x/candles", [("timeframe", "1h")], 3600.0) == 3600
    assert cache.ttl_seconds("/v1/assets/x/candles", [("timeframe", "1d")], 0.0) == 86400
    assert cache.ttl_seconds("/v1/market/overview", [("timeframe", "1d")], 0.0) == 3600


def test_valkey_down_gives_fresh_data_without_errors(env: Env) -> None:
    env.candles()
    env.valkey.down = True
    env.reader.add_candle("BTC")  # zdarzenie nie dociera (Valkey nie działa)
    with pytest.raises(ValkeyDown):
        env.inv.poll(block_ms=0)
    response = env.candles()
    assert response.status_code == 200
    assert state(response) == "goatcash; fwd=bypass"
    assert response.json()["items"][0]["ts"] == env.candles().json()["items"][0]["ts"]
    # odczyt cache przy zdrowym słuchaczu, ale Valkey pada w trakcie: też prosto z bazy
    env.valkey.down = False
    env.inv.connect()
    env.valkey.down = True
    assert state(env.candles()) == "goatcash; fwd=bypass"


def test_reconnect_invalidates_entries_from_before_outage(env: Env) -> None:
    env.candles()
    env.valkey.down = True
    with pytest.raises(ValkeyDown):
        env.inv.poll(block_ms=0)
    env.reader.add_candle("BTC")
    env.valkey.down = False
    env.valkey.xadd("BTC-USDT")
    env.valkey.stream.clear()  # zdarzenie przepadło (np. przycięty strumień)
    env.inv.poll(block_ms=0)  # ponowne połączenie
    response = env.candles()
    assert state(response) == "goatcash; fwd=miss"
    assert len(env.reader.extra) == 1


def test_stale_listener_bypasses_cache(env: Env) -> None:
    env.candles()
    assert state(env.candles()) == "goatcash; hit"
    env.mono.t += cache.STALE_AFTER_S  # słuchacz zawieszony: brak udanego XREAD
    assert not env.inv.healthy()
    assert state(env.candles()) == "goatcash; fwd=bypass"


def test_no_valkey_configured_is_plain_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOATCASH_VALKEY_URL", raising=False)
    client = TestClient(create_app(CountingReader()))
    response = cast(Response, client.get("/v1/assets"))  # pyright: ignore[reportUnknownMemberType]
    assert response.status_code == 200
    assert state(response) == "goatcash; fwd=bypass"


@pytest.mark.parametrize(
    ("url", "params"),
    [
        (f"/v1/assets/{UUID(int=1)}", {}),
        (f"/v1/assets/{BTC}/candles", {"timeframe": "1m"}),
        ("/v1/assets", {"cursor": "!!"}),
    ],
)
def test_errors_are_not_cached(env: Env, url: str, params: dict[str, str]) -> None:
    first = env.get(url, params=params)
    assert first.status_code >= 400
    assert not [k for k in env.valkey.ttls if ":resp:" in k]
    assert state(env.get(url, params=params)) == "goatcash; fwd=miss"


def test_different_queries_are_different_entries(env: Env) -> None:
    a = env.get(f"/v1/assets/{BTC}/candles", params={"timeframe": "1h", "limit": 2})
    b = env.get(f"/v1/assets/{BTC}/candles", params={"timeframe": "1h", "limit": 3})
    assert len(a.json()["items"]) == 2
    assert len(b.json()["items"]) == 3
    assert state(b) == "goatcash; fwd=miss"
    c = env.get(f"/v1/assets/{BTC}/candles?timeframe=1h&limit=2&limit=3")
    assert state(c) == "goatcash; fwd=miss"


def test_cached_response_keeps_security_and_cors_headers(env: Env) -> None:
    env.get("/v1/assets")
    hit = env.get("/v1/assets", headers={"Origin": APP_ORIGIN})
    assert state(hit) == "goatcash; hit"
    assert hit.headers["access-control-allow-origin"] == APP_ORIGIN
    assert hit.headers["x-content-type-options"] == "nosniff"
    assert hit.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert hit.headers["content-type"] == "application/json"
    other = env.get("/v1/assets", headers={"Origin": "https://evil.example"})
    assert state(other) == "goatcash; hit"
    assert "access-control-allow-origin" not in other.headers


def test_event_parsing() -> None:
    env_btc = {"event": json.dumps({"payload": {"symbol": "BTC-USDT"}})}
    assert cache.asset_from_event(env_btc) == BTC
    assert (
        cache.asset_from_event({b"event": json.dumps({"payload": {"symbol": "eth-USDT"}}).encode()})
        == ETH
    )
    for bad in (
        {},
        {"event": "nie-json"},
        {"event": "{}"},
        {"event": json.dumps({"payload": {"symbol": "BTCUSDT"}})},
    ):
        assert cache.asset_from_event(bad) is None


CACHED_APP = Env()
cached_schema = conformance_schema(CACHED_APP.client.app)  # pyright: ignore[reportArgumentType]


@cached_schema.parametrize()  # pyright: ignore[reportUntypedFunctionDecorator]
@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_schemathesis_with_cache(case: Any) -> None:
    CACHED_APP.mono.t += 0.001  # słuchacz zdrowy przez cały przebieg
    validate(case)
