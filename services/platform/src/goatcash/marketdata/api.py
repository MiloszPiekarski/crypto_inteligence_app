"""Publiczny interfejs modułu marketdata (roadmapa E4, ścieżka pracy: ADR-0008)."""

from goatcash.marketdata._impl.dq import DqConfig, DqEvent, DqResult, PairDq, is_stale
from goatcash.marketdata._impl.events import candle_closed, envelope, relay_outbox
from goatcash.marketdata._impl.gaps import ClassifiedGap, Gap, classify_gap, find_gaps
from goatcash.marketdata._impl.ingest import Ingest, InstrumentReport, instrument_report
from goatcash.marketdata._impl.pgstore import PostgresStore
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
    "HOUR_MS",
    "SOURCES",
    "BybitSource",
    "Candle",
    "ClassifiedGap",
    "DqConfig",
    "DqEvent",
    "DqResult",
    "Gap",
    "InMemoryStore",
    "Ingest",
    "InstrumentInfo",
    "InstrumentReport",
    "MarketDataSource",
    "MarketStore",
    "OkxSource",
    "PairDq",
    "PostgresStore",
    "RefCandle",
    "RetryPolicy",
    "SourceUnavailableError",
    "TimeRange",
    "Universe",
    "candle_closed",
    "classify_gap",
    "envelope",
    "find_gaps",
    "instrument_report",
    "is_stale",
    "load_universe",
    "reference_candles",
    "relay_outbox",
]
