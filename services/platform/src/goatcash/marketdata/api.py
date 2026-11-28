"""Publiczny interfejs modułu marketdata (roadmapa E4, ścieżka pracy: ADR-0008)."""

from goatcash.marketdata._impl.dq import DqConfig, DqEvent, DqResult, PairDq, is_stale
from goatcash.marketdata._impl.events import (
    STREAM as CANDLE_STREAM,
)
from goatcash.marketdata._impl.events import (
    OutboxEvent,
    StreamClient,
    candle_closed,
    envelope,
    relay_outbox,
    uuid7,
)
from goatcash.marketdata._impl.gaps import ClassifiedGap, Gap, classify_gap, find_gaps
from goatcash.marketdata._impl.ingest import Ingest, InstrumentReport, instrument_report
from goatcash.marketdata._impl.pgstore import PostgresStore
from goatcash.marketdata._impl.read import (
    ApiTimeframe,
    AssetInfo,
    Bar,
    InMemoryReader,
    MarketReader,
    OverviewRow,
    PostgresReader,
    aggregate,
    asset_public_id,
)
from goatcash.marketdata._impl.refprice import RefCandle, reference_candles
from goatcash.marketdata._impl.sources import (
    SOURCES,
    BybitSource,
    MarketDataSource,
    OkxSource,
    RetryPolicy,
    SourceUnavailableError,
)
from goatcash.marketdata._impl.store import InMemoryStore, MarketStore
from goatcash.marketdata._impl.types import HOUR_MS, Candle, InstrumentInfo, TimeRange
from goatcash.marketdata._impl.universe import Universe, load_universe

__all__ = [
    "CANDLE_STREAM",
    "HOUR_MS",
    "SOURCES",
    "ApiTimeframe",
    "AssetInfo",
    "Bar",
    "BybitSource",
    "Candle",
    "ClassifiedGap",
    "DqConfig",
    "DqEvent",
    "DqResult",
    "Gap",
    "InMemoryReader",
    "InMemoryStore",
    "Ingest",
    "InstrumentInfo",
    "InstrumentReport",
    "MarketDataSource",
    "MarketReader",
    "MarketStore",
    "OkxSource",
    "OutboxEvent",
    "OverviewRow",
    "PairDq",
    "PostgresReader",
    "PostgresStore",
    "RefCandle",
    "RetryPolicy",
    "SourceUnavailableError",
    "StreamClient",
    "TimeRange",
    "Universe",
    "aggregate",
    "asset_public_id",
    "candle_closed",
    "classify_gap",
    "envelope",
    "find_gaps",
    "instrument_report",
    "is_stale",
    "load_universe",
    "reference_candles",
    "relay_outbox",
    "uuid7",
]
