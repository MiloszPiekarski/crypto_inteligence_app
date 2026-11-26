# ccxt nie ma plików typów (pakiet generowany z JS); typy na granicy przez cast.
# pyright: reportMissingTypeStubs=false
"""Źródła danych rynkowych: interfejs `MarketDataSource` i adaptery OKX oraz Bybit (ccxt).

Roadmapa E4, zakres 1. W ścieżce pracy (ADR-0008) działają `instruments()` i `candles()`;
pozostałe metody interfejsu są zadeklarowane i zgłaszają `NotImplementedError`
(implementacja w ścieżce produktu: websockety, funding, OI, order book).

ccxt daje transport HTTP, ograniczanie tempa zapytań (`enableRateLimit`), mapowanie błędów
giełdy na wyjątki (np. 429 → `RateLimitExceeded`) i opis rynków z precyzją. Świece pobieramy
przez API niejawne ccxt (surowa odpowiedź giełdy), a nie `fetch_ohlcv`, bo `fetch_ohlcv`
zamienia ceny na float; my tworzymy `Decimal` prosto z tekstu odpowiedzi.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol, cast

import ccxt

from goatcash.marketdata._impl.normalize import (
    NormalizationError,
    candle_from_row,
    normalize_symbol,
    split_symbol,
    step_from_precision,
)
from goatcash.marketdata._impl.types import (
    TIMEFRAME_MS,
    Candle,
    InstrumentInfo,
    Timeframe,
    TimeRange,
)


class SourceUnavailableError(RuntimeError):
    """Giełda nie odpowiedziała poprawnie mimo ponowień (limit zapytań, sieć, przerwa)."""


class MarketDataSource(Protocol):
    """Źródło danych rynkowych jednej giełdy (roadmapa E4, punkt 1)."""

    @property
    def exchange(self) -> str: ...

    def instruments(self, symbols: Iterable[str]) -> list[InstrumentInfo]:
        """Instrumenty spot dla symboli `BAZA-KWOTOWANIE` (brak na giełdzie: pominięty)."""
        ...

    def candles(self, symbol: str, timeframe: Timeframe, time_range: TimeRange) -> list[Candle]:
        """Zamknięte świece z przedziału [start, end), rosnąco po czasie.

        Duplikaty z odpowiedzi giełdy zostają (stabilnie po czasie): usuwa je i rejestruje
        kontrola jakości (`dq`), żeby błąd giełdy był widoczny w `dq_events`.
        """
        ...

    def stream_candles(self, symbols: Iterable[str]) -> Iterable[Candle]:
        """Świece na żywo (websocket): ścieżka produktu."""
        ...

    def funding(self, symbol: str, time_range: TimeRange) -> list[object]:
        """Stopy finansowania: ścieżka produktu."""
        ...

    def open_interest(self, symbol: str, time_range: TimeRange) -> list[object]:
        """Otwarte pozycje: ścieżka produktu."""
        ...

    def orderbook_top(self, symbol: str, depth: int) -> object:
        """Order book top N: ścieżka produktu."""
        ...


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Ponowienia przy limicie zapytań i błędach sieci: wykładniczo, z górnym limitem."""

    max_attempts: int = 8
    base_delay_s: float = 1.0
    max_delay_s: float = 60.0
    sleep: Callable[[float], None] = time.sleep

    def delay(self, attempt: int) -> float:
        return float(min(self.max_delay_s, self.base_delay_s * (2**attempt)))


# Błędy przejściowe ccxt: NetworkError obejmuje DDoSProtection i RateLimitExceeded (429),
# RequestTimeout, ExchangeNotAvailable i OnMaintenance. Błędy żądania (BadRequest,
# BadSymbol) nie są ponawiane: to błąd naszego kodu albo konfiguracji.
TRANSIENT_ERRORS: tuple[type[BaseException], ...] = (ccxt.NetworkError,)


class _CcxtSpotSource:
    """Wspólna część adapterów: ccxt, ponowienia, stronicowanie, filtr świec zamkniętych."""

    exchange_id: str = ""
    page_limit: int = 100
    # Interwał ccxt → wartość parametru giełdy.
    interval_param: ClassVar[Mapping[str, str]] = {}

    def __init__(
        self,
        client: ccxt.Exchange | None = None,
        *,
        retry: RetryPolicy | None = None,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        self._client = client if client is not None else self._default_client()
        self._retry = retry or RetryPolicy()
        self._now_ms = now_ms or (lambda: int(time.time() * 1000))
        self._markets: dict[str, Any] | None = None

    @property
    def exchange(self) -> str:
        return self.exchange_id

    # --- do nadpisania w adapterze ---

    def _default_client(self) -> ccxt.Exchange:  # pragma: no cover (nadpisywane)
        raise NotImplementedError

    def _fetch_page(self, exchange_symbol: str, interval: str, start_ms: int) -> list[object]:
        """Jedna strona świec zaczynająca się od `start_ms` (surowe wiersze, dowolna kolejność)."""
        raise NotImplementedError  # pragma: no cover (nadpisywane)

    def _row_is_closed(self, row: Sequence[object], ts_ms: int, interval_ms: int) -> bool:
        return ts_ms + interval_ms <= self._now_ms()

    # --- wspólne ---

    def _call[T](self, fn: Callable[[], T]) -> T:
        last: BaseException | None = None
        for attempt in range(self._retry.max_attempts):
            try:
                return fn()
            except TRANSIENT_ERRORS as exc:
                last = exc
                if attempt + 1 < self._retry.max_attempts:
                    self._retry.sleep(self._retry.delay(attempt))
        raise SourceUnavailableError(
            f"{self.exchange_id}: brak poprawnej odpowiedzi po "
            f"{self._retry.max_attempts} próbach ({type(last).__name__}: {last})"
        ) from last

    def _load_markets(self) -> dict[str, Any]:
        if self._markets is None:
            load = cast(Callable[[], dict[str, Any]], getattr(self._client, "load_markets"))  # noqa: B009
            self._markets = self._call(load)
        return self._markets

    def _market(self, symbol: str) -> dict[str, Any] | None:
        base, quote = split_symbol(symbol)
        market = self._load_markets().get(f"{base}/{quote}")
        if market is None or market.get("type") != "spot":
            return None
        return cast(dict[str, Any], market)

    def instruments(self, symbols: Iterable[str]) -> list[InstrumentInfo]:
        result: list[InstrumentInfo] = []
        for symbol in symbols:
            market = self._market(symbol)
            if market is None:
                continue
            precision = cast(dict[str, object], market.get("precision") or {})
            result.append(
                InstrumentInfo(
                    exchange=self.exchange_id,
                    symbol=normalize_symbol(str(market["base"]), str(market["quote"])),
                    exchange_symbol=str(market["id"]),
                    base=str(market["base"]).upper(),
                    quote=str(market["quote"]).upper(),
                    price_tick=step_from_precision(precision.get("price"), "price"),
                    amount_step=step_from_precision(precision.get("amount"), "amount"),
                    active=bool(market.get("active", True)),
                )
            )
        return result

    def candles(self, symbol: str, timeframe: Timeframe, time_range: TimeRange) -> list[Candle]:
        interval_ms = TIMEFRAME_MS[timeframe]
        if time_range.start_ms % interval_ms or time_range.end_ms % interval_ms:
            raise ValueError(f"przedział niewyrównany do {timeframe}: {time_range}")
        market = self._market(symbol)
        if market is None:
            raise NormalizationError(f"{self.exchange_id}: brak instrumentu spot {symbol}")
        exchange_symbol = str(market["id"])
        interval = self.interval_param[timeframe]
        result: list[Candle] = []
        cursor = time_range.start_ms
        while cursor < time_range.end_ms:
            start = cursor
            rows = self._call(lambda s=start: self._fetch_page(exchange_symbol, interval, s))
            for raw in rows:
                row = cast(Sequence[object], raw)
                candle = candle_from_row(
                    row,
                    exchange=self.exchange_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    interval_ms=interval_ms,
                )
                in_range = time_range.start_ms <= candle.ts_ms < time_range.end_ms
                if in_range and self._row_is_closed(row, candle.ts_ms, interval_ms):
                    result.append(candle)
            cursor = start + self.page_limit * interval_ms
        return sorted(result, key=lambda c: c.ts_ms)

    def stream_candles(self, symbols: Iterable[str]) -> Iterable[Candle]:
        raise NotImplementedError("websockety świec: ścieżka produktu (ADR-0008)")

    def funding(self, symbol: str, time_range: TimeRange) -> list[object]:
        raise NotImplementedError("funding: ścieżka produktu (ADR-0008)")

    def open_interest(self, symbol: str, time_range: TimeRange) -> list[object]:
        raise NotImplementedError("open interest: ścieżka produktu (ADR-0008)")

    def orderbook_top(self, symbol: str, depth: int) -> object:
        raise NotImplementedError("order book: ścieżka produktu (ADR-0008)")


def _implicit(client: ccxt.Exchange, name: str) -> Callable[[dict[str, str]], dict[str, Any]]:
    """Metoda API niejawnego ccxt (generowana dynamicznie, więc bez typów)."""
    return cast(Callable[[dict[str, str]], dict[str, Any]], getattr(client, name))


class OkxSource(_CcxtSpotSource):
    """OKX: GET /api/v5/market/history-candles (do 100 świec, `after` = starsze niż ts)."""

    exchange_id = "okx"
    page_limit = 100
    interval_param: ClassVar[Mapping[str, str]] = {"1h": "1H"}

    def _default_client(self) -> ccxt.Exchange:
        return ccxt.okx({"enableRateLimit": True, "options": {"fetchMarkets": {"types": ["spot"]}}})

    def _fetch_page(self, exchange_symbol: str, interval: str, start_ms: int) -> list[object]:
        interval_ms = TIMEFRAME_MS["1h"]
        response = _implicit(self._client, "publicGetMarketHistoryCandles")(
            {
                "instId": exchange_symbol,
                "bar": interval,
                # `after`: rekordy starsze niż podany czas, czyli okno [start, start + 100 h).
                "after": str(start_ms + self.page_limit * interval_ms),
                "limit": str(self.page_limit),
            }
        )
        if response.get("code") != "0":
            raise NormalizationError(f"okx: kod odpowiedzi {response.get('code')!r}")
        return cast(list[object], response.get("data") or [])

    def _row_is_closed(self, row: Sequence[object], ts_ms: int, interval_ms: int) -> bool:
        # Pole `confirm` (9. kolumna): "1" = świeca zamknięta.
        confirmed = len(row) < 9 or row[8] == "1"  # noqa: PLR2004
        return confirmed and super()._row_is_closed(row, ts_ms, interval_ms)


class BybitSource(_CcxtSpotSource):
    """Bybit: GET /v5/market/kline, category=spot (do 1000 świec, `start`/`end` włącznie)."""

    exchange_id = "bybit"
    page_limit = 1000
    interval_param: ClassVar[Mapping[str, str]] = {"1h": "60"}

    def _default_client(self) -> ccxt.Exchange:
        return ccxt.bybit(
            {"enableRateLimit": True, "options": {"fetchMarkets": {"types": ["spot"]}}}
        )

    def _fetch_page(self, exchange_symbol: str, interval: str, start_ms: int) -> list[object]:
        interval_ms = TIMEFRAME_MS["1h"]
        response = _implicit(self._client, "publicGetV5MarketKline")(
            {
                "category": "spot",
                "symbol": exchange_symbol,
                "interval": interval,
                "start": str(start_ms),
                "end": str(start_ms + (self.page_limit - 1) * interval_ms),
                "limit": str(self.page_limit),
            }
        )
        if response.get("retCode") not in (0, "0"):
            raise NormalizationError(f"bybit: retCode {response.get('retCode')!r}")
        result = cast(dict[str, object], response.get("result") or {})
        return cast(list[object], result.get("list") or [])


SOURCES: dict[str, type[_CcxtSpotSource]] = {"okx": OkxSource, "bybit": BybitSource}
