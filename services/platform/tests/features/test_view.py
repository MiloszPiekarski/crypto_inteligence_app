"""`MarketView` i źródło w pamięci: czas, walidacja wejścia, filtr `known_at`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fs_helpers import ETH, T0, H, gbm_bars

from goatcash.features.api import InMemoryRefSource, MarketView, RefBar
from goatcash.marketdata.api import RefCandle


def test_datetime_as_of_and_known_at() -> None:
    src = InMemoryRefSource({ETH: gbm_bars(10, seed=1)})
    as_of = datetime.fromtimestamp(T0 / 1000, tz=UTC) + timedelta(hours=5)
    view = MarketView(src, as_of, known_at=as_of)
    assert view.as_of_ms == T0 + 5 * H
    assert view.bars(ETH).height == 4  # świeca 4 zapisana minutę po zamknięciu (5 h + 60 s)
    assert MarketView(src, as_of).bars(ETH).height == 5
    with pytest.raises(ValueError, match="bez strefy"):
        MarketView(src, datetime(2024, 1, 1))


def test_source_rejects_duplicates_and_unaligned_bars() -> None:
    bar = gbm_bars(1, seed=1)[0]
    with pytest.raises(ValueError, match="powtórzona"):
        InMemoryRefSource({ETH: [bar, bar]})
    shifted = RefBar(bar.ts_ms + 1, 1, 1, 1, 1, 1, bar.ingested_at_ms)
    with pytest.raises(ValueError, match="niewyrównana"):
        InMemoryRefSource({ETH: [shifted]})


def test_from_ref_candles_converts_decimals() -> None:
    ref = RefCandle(
        base="ETH",
        quote="USDT",
        timeframe="1h",
        ts_ms=T0,
        open=Decimal("2000.1"),
        high=Decimal("2001"),
        low=Decimal("1999.5"),
        close=Decimal("2000.75"),
        volume=Decimal("12.5"),
        sources=("bybit", "okx"),
        source="median",
    )
    src = InMemoryRefSource.from_ref_candles(
        [ref], ingested_at_ms={("ETH", "USDT", T0): T0 + 2 * H}
    )
    (bar,) = src.ref_bars(ETH, close_until_ms=T0 + H, known_at_ms=None)
    assert bar == RefBar(T0, 2000.1, 2001.0, 1999.5, 2000.75, 12.5, T0 + 2 * H)
    assert src.ref_bars(ETH, close_until_ms=T0 + H, known_at_ms=T0 + H) == []
