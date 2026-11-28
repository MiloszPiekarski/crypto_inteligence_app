"""Endpointy rynkowe API v1 na danych w pamięci (E6, bramka G6p, `api-data`).

- świece 1h z API = `candles_ref` (te same liczby dziesiętne);
- 4h i 1d zgodne z niezależnym przeliczeniem (osobna pętla po godzinach okresu), okres
  z brakującą świecą 1h nie jest zwracany (decyzja D3, uzupełnienie właściciela 28.11.2026);
- paginacja kursorowa (Hypothesis): przejście wszystkich stron = pełny zbiór, bez dubli
  i bez braków, w kolejności; kursor z innego zasobu albo uszkodzony = 400;
- przegląd rynku: zamknięcie, zmiana i wolumen 24 h, najgorszy status DQ;
- błędy: 404, 422 (także interwał 1m usunięty w D3), 503 bez bazy i przy awarii bazy, 500.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import psycopg
import pytest
from api_data import DQ, ETH_MISSING_MS, NAMES, QUOTE, Failing, reader, refs
from fastapi.testclient import TestClient
from httpx import Response
from hypothesis import given, settings
from hypothesis import strategies as st

from goatcash.http_api.app import create_app
from goatcash.http_api.market import dec
from goatcash.marketdata.api import HOUR_MS, RefCandle, asset_public_id

client = TestClient(create_app(reader()))
PROBLEM = "application/problem+json"


def get(url: str, **params: Any) -> Any:
    response = cast(Response, client.get(url, params=params))  # pyright: ignore[reportUnknownMemberType]
    return response


def ok(url: str, **params: Any) -> Any:
    response = get(url, **params)
    assert response.status_code == 200, response.text
    return response.json()


def ts(ms: int) -> str:
    return (
        (datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=ms))
        .isoformat()
        .replace("+00:00", "Z")
    )


def iso_ms(value: str) -> int:
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def candles_url(symbol: str) -> str:
    return f"/v1/assets/{asset_public_id(symbol)}/candles"


def all_candles(symbol: str, timeframe: str, limit: int = 200) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor = None
    for _ in range(10 * 24 * 10):  # więcej stron niż świec = kursor stoi w miejscu
        params: dict[str, Any] = {"timeframe": timeframe, "limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        page = ok(candles_url(symbol), **params)
        items += page["items"]
        cursor = page["next_cursor"]
        if cursor is None:
            return items
    pytest.fail("paginacja się nie kończy (kursor nie przesuwa pozycji)")


def reference(symbol: str, hours: int) -> list[dict[str, Any]]:
    """Niezależne przeliczenie: dla każdego okresu UTC sprawdzamy wprost każdą z jego godzin."""
    by_ts = {r.ts_ms: r for r in refs() if r.base == symbol}
    if not by_ts:
        return []
    span = hours * HOUR_MS
    first = min(by_ts) // span * span
    out: list[dict[str, Any]] = []
    start = first
    while start <= max(by_ts):
        members: list[RefCandle] = []
        for h in range(hours):
            candle = by_ts.get(start + h * HOUR_MS)
            if candle is None:
                break
            members.append(candle)
        if len(members) == hours:
            out.append(
                {
                    "ts": ts(start),
                    "open": members[0].open,
                    "high": max(m.high for m in members),
                    "low": min(m.low for m in members),
                    "close": members[-1].close,
                    "volume": sum(m.volume for m in members),
                }
            )
        start += span
    return list(reversed(out))


def as_decimals(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = ("open", "high", "low", "close", "volume")
    return [{**c, **{k: Decimal(c[k]) for k in keys}} for c in items]


@pytest.mark.parametrize("symbol", ["BTC", "ETH", "SOL", "DOGE"])
@pytest.mark.parametrize(("timeframe", "hours"), [("1h", 1), ("4h", 4), ("1d", 24)])
def test_candles_match_independent_reference(symbol: str, timeframe: str, hours: int) -> None:
    got = all_candles(symbol, timeframe)
    assert as_decimals(got) == reference(symbol, hours)
    if timeframe == "1h":
        # 1h wprost z candles_ref: te same liczby (także zapis tekstowy bez wykładnika)
        rows = sorted((r for r in refs() if r.base == symbol), key=lambda r: -r.ts_ms)
        assert [c["close"] for c in got] == [format(r.close, "f") for r in rows]


def test_period_with_missing_hour_is_not_returned() -> None:
    four = {c["ts"] for c in all_candles("ETH", "4h")}
    day = {c["ts"] for c in all_candles("ETH", "1d")}
    start4 = ETH_MISSING_MS // (4 * HOUR_MS) * (4 * HOUR_MS)
    start1d = ETH_MISSING_MS // (24 * HOUR_MS) * (24 * HOUR_MS)
    assert ts(start4) not in four
    assert ts(start4 - 4 * HOUR_MS) in four
    assert ts(start4 + 4 * HOUR_MS) in four
    assert ts(start1d) not in day
    assert ts(start1d - 24 * HOUR_MS) in day
    # mutacja: ta sama doba z kompletem świec BTC jest zwracana
    assert ts(start1d) in {c["ts"] for c in all_candles("BTC", "1d")}


def test_candles_newest_first_and_aligned_to_utc() -> None:
    for timeframe, hours in (("1h", 1), ("4h", 4), ("1d", 24)):
        stamps = [iso_ms(c["ts"]) for c in all_candles("BTC", timeframe)]
        assert stamps == sorted(stamps, reverse=True)
        assert all(s % (hours * HOUR_MS) == 0 for s in stamps)


@settings(max_examples=60, deadline=None)
@given(
    symbol=st.sampled_from(["BTC", "ETH", "SOL"]),
    timeframe=st.sampled_from(["1h", "4h", "1d"]),
    limit=st.integers(min_value=1, max_value=200),
)
def test_pagination_walk_equals_full_set(symbol: str, timeframe: str, limit: int) -> None:
    full = all_candles(symbol, timeframe, limit=200)
    walked = all_candles(symbol, timeframe, limit=limit)
    assert walked == full
    assert len({c["ts"] for c in walked}) == len(walked)


@settings(max_examples=20, deadline=None)
@given(limit=st.integers(min_value=1, max_value=6))
def test_assets_pagination(limit: int) -> None:
    symbols: list[str] = []
    cursor = None
    for _ in range(len(NAMES) + 1):
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        page = ok("/v1/assets", **params)
        assert len(page["items"]) <= limit
        symbols += [a["symbol"] for a in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    else:
        pytest.fail("paginacja aktywów się nie kończy")
    assert symbols == sorted(set(NAMES) - {QUOTE})


def test_asset_ids_are_public_uuid_from_symbol() -> None:
    items = ok("/v1/assets")["items"]
    assert {a["id"] for a in items} == {str(asset_public_id(a["symbol"])) for a in items}
    btc = ok(f"/v1/assets/{asset_public_id('BTC')}")
    assert btc == {"id": str(asset_public_id("BTC")), "symbol": "BTC", "name": "Bitcoin"}
    assert len({asset_public_id(s) for s in NAMES}) == len(NAMES)


def test_overview() -> None:
    items = {i["asset"]["symbol"]: i for i in ok("/v1/market/overview")["items"]}
    assert set(items) == {"BTC", "ETH", "SOL"}  # DOGE bez świec nie ma w przeglądzie
    for symbol, item in items.items():
        rows = {r.ts_ms: r for r in refs() if r.base == symbol}
        last = max(rows)
        assert item["ts"] == ts(last)
        assert Decimal(item["close"]) == rows[last].close
        ago = rows.get(last - 24 * HOUR_MS)
        expected = None if ago is None else float(rows[last].close / ago.close - 1)
        assert item["change_24h"] == expected
        window = [rows.get(last - i * HOUR_MS) for i in range(24)]
        if all(w is not None for w in window):
            assert Decimal(item["volume_24h"]) == sum(w.volume for w in window if w is not None)
        else:
            assert item["volume_24h"] is None
    assert items["ETH"]["volume_24h"] is None
    assert items["ETH"]["change_24h"] is not None
    assert items["SOL"]["change_24h"] is not None
    assert items["BTC"]["dq_status"] == "ok"
    assert items["ETH"]["dq_status"] == "degraded"
    assert items["SOL"]["dq_status"] == "stale"
    assert set(DQ) == set(items)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (Decimal("1E+3"), "1000"),
        (Decimal("0E-8"), "0.00000000"),
        (Decimal("12.50"), "12.50"),
        (Decimal("0.000000012"), "0.000000012"),
    ],
)
def test_decimal_text_without_exponent(value: Decimal, text: str) -> None:
    assert dec(value) == text


def assert_problem(response: Any, status: int) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == PROBLEM
    body = response.json()
    assert body["status"] == status
    assert body["type"] == "about:blank"
    assert body["title"]
    return body


UNKNOWN = "0193a4f2-7c1e-7a3b-9d2e-000000000099"


@pytest.mark.parametrize(
    ("url", "params", "status"),
    [
        (f"/v1/assets/{UNKNOWN}", {}, 404),
        (f"/v1/assets/{UNKNOWN}/candles", {"timeframe": "1h"}, 404),
        ("/v1/assets/nie-uuid", {}, 422),
        (candles_url("BTC"), {}, 422),
        (candles_url("BTC"), {"timeframe": "1m"}, 422),
        (candles_url("BTC"), {"timeframe": "1h", "limit": 0}, 422),
        (candles_url("BTC"), {"timeframe": "1h", "limit": 201}, 422),
        ("/v1/assets", {"limit": 201}, 422),
        ("/v1/assets", {"cursor": "!!!"}, 400),
        ("/v1/assets", {"cursor": "Zm9v"}, 400),
        (candles_url("BTC"), {"timeframe": "1h", "cursor": "x" * 201}, 422),
        ("/v1/nie-ma", {}, 404),
    ],
)
def test_errors_are_problem_details(url: str, params: dict[str, Any], status: int) -> None:
    assert_problem(get(url, **params), status)


def test_cursor_bound_to_asset_and_timeframe() -> None:
    page = ok(candles_url("BTC"), timeframe="1h", limit=2)
    cursor = page["next_cursor"]
    assert cursor
    assert ok(candles_url("BTC"), timeframe="1h", limit=2, cursor=cursor)["items"]
    assert_problem(get(candles_url("BTC"), timeframe="4h", cursor=cursor), 400)
    assert_problem(get(candles_url("ETH"), timeframe="1h", cursor=cursor), 400)
    assets_cursor = ok("/v1/assets", limit=1)["next_cursor"]
    assert_problem(get(candles_url("BTC"), timeframe="1h", cursor=assets_cursor), 400)
    assert_problem(get("/v1/assets", cursor=cursor), 400)


def test_validation_problem_names_the_parameter() -> None:
    body = assert_problem(get(candles_url("BTC"), timeframe="1m"), 422)
    assert "timeframe" in body["detail"]


def test_no_database_configured_gives_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOATCASH_DATABASE_URL", raising=False)
    bare = TestClient(create_app())
    assert bare.get("/v1/health").status_code == 200  # pyright: ignore[reportUnknownMemberType]
    for url in ("/v1/assets", "/v1/market/overview", f"/v1/assets/{UNKNOWN}"):
        assert_problem(bare.get(url), 503)  # pyright: ignore[reportUnknownMemberType]


def test_database_outage_gives_503_with_retry_after() -> None:
    broken = TestClient(create_app(Failing(psycopg.OperationalError("połączenie zerwane"))))
    response = cast(Response, broken.get("/v1/assets"))  # pyright: ignore[reportUnknownMemberType]
    body = assert_problem(response, 503)
    assert response.headers["retry-after"] == "30"
    assert "zerwane" not in response.text  # szczegóły awarii nie wychodzą na zewnątrz
    assert body["detail"]


def test_unhandled_error_gives_problem_500_without_details() -> None:
    broken = TestClient(
        create_app(Failing(RuntimeError("sekretny szczegół"))), raise_server_exceptions=False
    )
    response = cast(Response, broken.get("/v1/market/overview"))  # pyright: ignore[reportUnknownMemberType]
    assert_problem(response, 500)
    assert "sekretny" not in response.text
