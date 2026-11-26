"""Normalizacja na nagranych odpowiedziach giełd (bramka G4p, kryterium 1: 100% zgodności).

Oczekiwany wynik liczymy niezależnie od adaptera: wprost z surowej treści nagranej
odpowiedzi (JSON giełdy), bez ccxt i bez kodu normalizacji. Porównujemy każde pole i jego
typ: symbol `BAZA-KWOTOWANIE`, czas UTC w ms wyrównany do godziny, ceny i wolumen jako
`Decimal` z dokładnie tym samym zapisem dziesiętnym co w odpowiedzi giełdy.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, cast

import pytest
from md_helpers import FIXTURES, cassette, recorded_exchanges, recorded_ms, replay_source

from goatcash.marketdata._impl.normalize import (
    NormalizationError,
    candle_from_row,
    normalize_symbol,
    parse_decimal,
    parse_ts_ms,
    step_from_precision,
)
from goatcash.marketdata._impl.record import normalization_windows, series_window
from goatcash.marketdata.api import HOUR_MS, Candle, load_universe

UNIVERSE = load_universe()
EXCHANGES = recorded_exchanges()


def raw_instruments(exchange: str) -> list[dict[str, Any]]:
    body = json.loads(cassette(exchange, "instruments").interactions[0].body)
    if exchange == "okx":
        return cast(list[dict[str, Any]], body["data"])
    return cast(list[dict[str, Any]], body["result"]["list"])


def expected_instrument(exchange: str, raw: dict[str, Any]) -> dict[str, object]:
    if exchange == "okx":
        return {
            "symbol": f"{raw['baseCcy']}-{raw['quoteCcy']}",
            "exchange_symbol": raw["instId"],
            "price_tick": Decimal(raw["tickSz"]),
            "amount_step": Decimal(raw["lotSz"]),
            "active": raw["state"] == "live",
        }
    return {
        "symbol": f"{raw['baseCoin']}-{raw['quoteCoin']}",
        "exchange_symbol": raw["symbol"],
        "price_tick": Decimal(raw["priceFilter"]["tickSize"]),
        "amount_step": Decimal(raw["lotSizeFilter"]["basePrecision"]),
        "active": raw["status"] == "Trading",
    }


def raw_rows(exchange: str, body: str) -> list[list[str]]:
    data = json.loads(body)
    if exchange == "okx":
        return cast(list[list[str]], data["data"])
    return cast(list[list[str]], data["result"]["list"])


def expected_candles(exchange: str, name: str, symbol: str, start: int, end: int) -> list[Candle]:
    c = cassette(exchange, name)
    now = recorded_ms(c)
    out: dict[int, Candle] = {}
    for interaction in c.interactions:
        for row in raw_rows(exchange, interaction.body):
            ts = int(row[0])
            closed = ts + HOUR_MS <= now and (exchange != "okx" or row[8] == "1")
            if start <= ts < end and closed:
                out[ts] = Candle(
                    exchange=exchange,
                    symbol=symbol,
                    timeframe="1h",
                    ts_ms=ts,
                    open=Decimal(row[1]),
                    high=Decimal(row[2]),
                    low=Decimal(row[3]),
                    close=Decimal(row[4]),
                    volume=Decimal(row[5]),
                )
    return [out[ts] for ts in sorted(out)]


def assert_same(
    actual: list[Candle], expected: list[Candle], rows_text: dict[int, list[str]]
) -> None:
    assert [c.ts_ms for c in actual] == [c.ts_ms for c in expected]
    for a, e in zip(actual, expected, strict=True):
        assert a == e
        assert a.ts_ms % HOUR_MS == 0
        assert type(a.ts_ms) is int
        raw = rows_text[a.ts_ms]
        for value, text in zip((a.open, a.high, a.low, a.close, a.volume), raw[1:6], strict=True):
            assert type(value) is Decimal
            assert str(value) == text  # dokładnie ten sam zapis co u giełdy (bez floatów)


@pytest.mark.parametrize("exchange", EXCHANGES)
def test_instruments_all_universe_pairs_fields_and_types(exchange: str) -> None:
    source, _ = replay_source(exchange, [])
    infos = source.instruments(UNIVERSE.symbols)
    assert {i.symbol for i in infos} == set(UNIVERSE.symbols)
    raw = {
        expected_instrument(exchange, r)["symbol"]: expected_instrument(exchange, r)
        for r in raw_instruments(exchange)
    }
    for info in infos:
        e = raw[info.symbol]
        assert info.exchange == exchange
        assert info.exchange_symbol == e["exchange_symbol"]
        assert info.price_tick == e["price_tick"]
        assert info.amount_step == e["amount_step"]
        assert type(info.price_tick) is Decimal
        assert type(info.amount_step) is Decimal
        assert info.active is e["active"] is True
        assert (info.base, info.quote) == tuple(info.symbol.split("-"))


@pytest.mark.parametrize("exchange", EXCHANGES)
@pytest.mark.parametrize("symbol", UNIVERSE.symbols)
def test_candles_match_recorded_response(exchange: str, symbol: str) -> None:
    name = f"candles_{symbol}"
    source, session = replay_source(exchange, [name])
    rows_text = {
        int(r[0]): r
        for i in cassette(exchange, name).interactions
        for r in raw_rows(exchange, i.body)
    }
    total = 0
    for window in normalization_windows(UNIVERSE):
        actual = source.candles(symbol, "1h", window.time_range)
        expected = expected_candles(
            exchange, name, symbol, window.time_range.start_ms, window.time_range.end_ms
        )
        assert len(expected) > 0
        assert_same(actual, expected, rows_text)
        total += len(actual)
    # Wszystkie nagrane świece okien zostały znormalizowane (żadna nie zginęła po drodze).
    assert total == sum(
        1
        for ts in rows_text
        if any(
            w.time_range.start_ms <= ts < w.time_range.end_ms
            for w in normalization_windows(UNIVERSE)
        )
    )
    assert session.requests  # odpowiedzi pochodziły z kaset, nie z sieci


@pytest.mark.parametrize("exchange", EXCHANGES)
def test_series_cassettes_normalize(exchange: str) -> None:
    for path in sorted((FIXTURES / exchange).glob("series_*.json")):
        symbol = path.stem.removeprefix("series_")
        source, _ = replay_source(exchange, [path.stem])
        tr = series_window()
        actual = source.candles(symbol, "1h", tr)
        expected = expected_candles(exchange, path.stem, symbol, tr.start_ms, tr.end_ms)
        assert actual == expected
        assert len(actual) > 1900  # 2000 h; luki po stronie giełdy dopuszczalne, ale nieliczne


@pytest.mark.fixtures_complete
def test_fixtures_cover_both_exchanges_for_g4p() -> None:
    # Bramka G4p wymaga nagrań obu giełd. Bybit blokuje kraj sesji asystenta (403
    # CloudFront, 26.11.2026), więc kasety Bybit nagrywamy z serwera w Amsterdamie (PR 2 E4).
    # Ten test jest w bramce G4p (make marketdata-fixtures-test), poza `make test`.
    missing = [ex for ex in ("okx", "bybit") if ex not in EXCHANGES]
    assert not missing, f"brak kaset giełd: {missing}"
    for ex in ("okx", "bybit"):
        names = {p.stem for p in (FIXTURES / ex).glob("*.json")}
        assert {f"candles_{s}" for s in UNIVERSE.symbols} <= names


# --- przypadki brzegowe normalizacji (bez kaset) ---


def test_symbol_normalization() -> None:
    assert normalize_symbol("btc", "usdt") == "BTC-USDT"
    with pytest.raises(NormalizationError):
        normalize_symbol("BTC/", "USDT")


@pytest.mark.parametrize("bad", [1.5, None, "1,5", "nan", "inf", "", " 1", "0x10", True])
def test_decimal_rejects_non_text_numbers(bad: object) -> None:
    with pytest.raises(NormalizationError):
        parse_decimal(bad, "close")


def test_decimal_keeps_exact_text() -> None:
    assert str(parse_decimal("0.00001234", "close")) == "0.00001234"
    assert parse_decimal("-1", "volume") == Decimal(-1)  # ujemny wolumen odrzuca DQ, nie parser


def test_ts_must_be_aligned_and_integer() -> None:
    assert parse_ts_ms("1672531200000", HOUR_MS) == 1_672_531_200_000
    for bad in ("1672531200001", "1.6e12", 1.0, True, "-3600000"):
        with pytest.raises(NormalizationError):
            parse_ts_ms(bad, HOUR_MS)


def test_row_too_short() -> None:
    with pytest.raises(NormalizationError):
        candle_from_row(
            ["1", "2"], exchange="okx", symbol="BTC-USDT", timeframe="1h", interval_ms=HOUR_MS
        )


def test_precision_step_from_float_without_noise() -> None:
    assert step_from_precision(1e-08, "amount") == Decimal("1E-8")
    assert step_from_precision(0.1, "price") == Decimal("0.1")
    for bad in (None, 0, -0.1, True):
        with pytest.raises(NormalizationError):
            step_from_precision(bad, "price")
