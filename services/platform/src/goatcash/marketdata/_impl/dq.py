"""Kontrola jakości danych (Data Quality Sentinel, ścieżka pracy): roadmapa E4, punkt 6.

Reguły dla świec 1 h jednej pary z dwóch giełd, przetwarzanych chronologicznie:

- odrzucenie (`rejected`, świeca nie trafia do bazy): cena ≤ 0, niespójne OHLC
  (low ≤ open, close ≤ high), wolumen < 0, duplikat (ten sam czas drugi raz, także względem
  świec już przetworzonych);
- oznaczenie (`flagged`, świeca zostaje, ale nie liczy się do ceny referencyjnej ani do
  statystyk): odchylenie od drugiej giełdy > 3% (oznaczamy tę giełdę, której cena bardziej
  odskoczyła od jej własnego poprzedniego zamknięcia), skok ceny > 8 odchyleń standardowych
  stóp zwrotu z poprzednich 168 h (bez potwierdzenia przez drugą giełdę);
- nieaktualność (`stale`): brak nowej świecy 1 h dłużej niż 2 h po jej zamknięciu
  (`is_stale`, wynik w `dq_status`).

Brak zaglądania w przyszłość: werdykt dla świecy w chwili t zależy wyłącznie od świec
z czasem ≤ t (własna historia i świeca drugiej giełdy z tego samego t). Pilnuje tego test
właściwości (prefiks danych daje te same werdykty co całość).
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from goatcash.marketdata._impl.types import HOUR_MS, Candle

Decision = Literal["rejected", "flagged", "repaired"]

# Rodzaje zdarzeń DQ (kolumna dq_events.kind).
NONPOSITIVE_PRICE = "nonpositive_price"
OHLC_INCONSISTENT = "ohlc_inconsistent"
NEGATIVE_VOLUME = "negative_volume"
DUPLICATE = "duplicate"
CROSS_DEVIATION = "cross_exchange_deviation"
PRICE_SPIKE = "price_spike"
GAP_EXCHANGE = "gap_exchange"
GAP_OURS = "gap_ours"

DATASET = "candles_1h"


@dataclass(frozen=True, slots=True)
class DqConfig:
    """Progi reguł (roadmapa E4, punkt 8; nieaktualność 2 h: ścieżka pracy, REST co 1 h)."""

    max_deviation: Decimal = Decimal("0.03")
    spike_sigmas: float = 8.0
    window: int = 168  # stóp zwrotu (7 dni świec 1 h)
    min_window: int = 48  # mniej historii: reguła skoku nie ocenia (za mało danych)
    # Dolna granica sigma (0,01%, rząd jednego kroku ceny): przy płaskiej serii sigma = 0 i każdy
    # ruch byłby „skokiem”.
    min_sigma: float = 1e-4
    # Po tylu kolejnych skokach na spójnym nowym poziomie przyjmujemy nowy poziom ceny
    # (zmiana poziomu, nie pojedynczy błędny odczyt); świece pozostają oznaczone.
    level_shift_after: int = 3
    stale_after_ms: int = 2 * HOUR_MS


@dataclass(frozen=True, slots=True)
class DqEvent:
    """Zdarzenie kontroli jakości (wiersz dq_events)."""

    exchange: str
    symbol: str
    ts_ms: int
    kind: str
    decision: Decision
    details: Mapping[str, str] = field(default_factory=dict[str, str])


@dataclass(slots=True)
class DqResult:
    """Wynik kontroli partii: świece do zapisu, oznaczone (exchange, ts) i zdarzenia."""

    accepted: list[Candle] = field(default_factory=list[Candle])
    flagged: set[tuple[str, int]] = field(default_factory=set[tuple[str, int]])
    events: list[DqEvent] = field(default_factory=list[DqEvent])

    def good(self) -> list[Candle]:
        """Świece zapisane i nieoznaczone (wejście ceny referencyjnej)."""
        return [c for c in self.accepted if (c.exchange, c.ts_ms) not in self.flagged]


@dataclass(slots=True)
class _SourceState:
    last_ts: int | None = None  # ostatnia przetworzona (także odrzucona) świeca
    last_close: Decimal | None = None  # ostatnie zamknięcie świecy nieoznaczonej
    returns: deque[float] = field(default_factory=deque[float])
    spike_run: int = 0
    run_close: Decimal | None = None


def row_errors(candle: Candle) -> list[str]:
    """Błędy pojedynczej świecy, niezależne od innych świec."""
    errors: list[str] = []
    prices = (candle.open, candle.high, candle.low, candle.close)
    if any(p <= 0 for p in prices):
        errors.append(NONPOSITIVE_PRICE)
    if not (
        candle.low <= candle.open <= candle.high
        and candle.low <= candle.close <= candle.high
        and candle.low <= candle.high
    ):
        errors.append(OHLC_INCONSISTENT)
    if candle.volume < 0:
        errors.append(NEGATIVE_VOLUME)
    return errors


def population_std(values: Iterable[float]) -> float:
    """Odchylenie standardowe populacji (float, `fsum`): zależy tylko od zawartości okna."""
    data = list(values)
    mean = math.fsum(data) / len(data)
    return math.sqrt(math.fsum((x - mean) ** 2 for x in data) / len(data))


def relative_deviation(a: Decimal, b: Decimal) -> Decimal:
    """|a - b| / średnia(a, b): symetryczne odchylenie dwóch cen."""
    return abs(a - b) / ((a + b) / 2)


def is_stale(last_ts_ms: int | None, now_ms: int, config: DqConfig | None = None) -> bool:
    """Brak nowej świecy 1 h dłużej niż `stale_after` po zamknięciu ostatniej."""
    cfg = config or DqConfig()
    if last_ts_ms is None:
        return True
    return now_ms - (last_ts_ms + HOUR_MS) > cfg.stale_after_ms


class PairDq:
    """Kontrola jakości jednej pary (np. BTC-USDT) na kilku giełdach, chronologicznie.

    Stan (ostatnie zamknięcie i okno stóp zwrotu każdej giełdy) przechodzi między
    partiami, więc partie można podawać kolejno (uzupełnianie historii oknami).
    """

    def __init__(self, exchanges: Sequence[str], config: DqConfig | None = None) -> None:
        self.config = config or DqConfig()
        self._state = {
            ex: _SourceState(returns=deque(maxlen=self.config.window)) for ex in exchanges
        }

    def warm_up(self, exchange: str, history: Sequence[Candle]) -> None:
        """Stan z wcześniej zapisanych, nieoznaczonych świec (rosnąco po czasie)."""
        state = self._state[exchange]
        for candle in history:
            if state.last_close is not None:
                state.returns.append(math.log(float(candle.close / state.last_close)))
            state.last_close = candle.close
            state.last_ts = candle.ts_ms

    def _sigma(self, state: _SourceState) -> float | None:
        if len(state.returns) < self.config.min_window:
            return None
        return max(population_std(state.returns), self.config.min_sigma)

    def process(
        self,
        candles: Iterable[Candle],
        context: Mapping[int, Mapping[str, Candle]] | None = None,
    ) -> DqResult:
        """Sprawdza świece (dowolna kolejność wejścia; przetwarzanie rosnąco po czasie).

        `context`: świece już zapisane (ts → giełda → świeca) używane tylko do porównania
        z drugą giełdą, np. przy uzupełnianiu luki jednej giełdy; nie dają zdarzeń.
        """
        result = DqResult()
        by_ts: dict[int, list[Candle]] = {}
        for candle in candles:
            by_ts.setdefault(candle.ts_ms, []).append(candle)
        for ts in sorted(by_ts):
            self._process_ts(ts, by_ts[ts], (context or {}).get(ts, {}), result)
        return result

    def _process_ts(
        self,
        ts: int,
        candles: list[Candle],
        context: Mapping[str, Candle],
        result: DqResult,
    ) -> None:
        survivors = self._row_checks(ts, candles, result)
        result.accepted.extend(survivors.values())
        # Stopa zwrotu każdej świecy względem ostatniego nieoznaczonego zamknięcia tej giełdy.
        returns: dict[str, float | None] = {}
        for ex, candle in survivors.items():
            last = self._state[ex].last_close
            returns[ex] = None if last is None else math.log(float(candle.close / last))
        # Porównanie giełd: świeca z tego samego t (z partii albo z kontekstu).
        peers: dict[str, Candle] = {**context, **survivors}
        deviating = self._cross_checks(survivors, peers, returns, result)
        for ex, candle in survivors.items():
            state = self._state[ex]
            r = returns[ex]
            sigma = self._sigma(state)
            confirmers = {o: c for o, c in peers.items() if o not in deviating and o != ex}
            flagged = ex in deviating or self._is_spike(candle, r, sigma, confirmers, result)
            if flagged:
                result.flagged.add((ex, ts))
                self._track_level_shift(state, candle, sigma)
                continue
            state.spike_run = 0
            state.run_close = None
            if r is not None:
                state.returns.append(r)
            state.last_close = candle.close

    def _row_checks(self, ts: int, candles: list[Candle], result: DqResult) -> dict[str, Candle]:
        """Duplikaty i błędy pojedynczej świecy; zwraca świece, które przeszły."""
        survivors: dict[str, Candle] = {}
        for candle in candles:
            state = self._state[candle.exchange]
            if candle.exchange in survivors or (state.last_ts is not None and ts <= state.last_ts):
                result.events.append(_event(candle, DUPLICATE, "rejected"))
                continue
            errors = row_errors(candle)
            state.last_ts = ts
            if errors:
                result.events.extend(_event(candle, kind, "rejected") for kind in errors)
                continue
            survivors[candle.exchange] = candle
        return survivors

    def _cross_checks(
        self,
        survivors: Mapping[str, Candle],
        peers: Mapping[str, Candle],
        returns: Mapping[str, float | None],
        result: DqResult,
    ) -> set[str]:
        """Odchylenie > 3% od drugiej giełdy: oznaczamy tę, która bardziej odskoczyła."""
        deviating: set[str] = set()
        for ex, candle in survivors.items():
            for other_ex, other in peers.items():
                if other_ex == ex:
                    continue
                dev = relative_deviation(candle.close, other.close)
                if dev <= self.config.max_deviation:
                    continue
                mine = returns.get(ex)
                # Świeca z kontekstu jest już sprawdzona i zapisana: traktujemy ją jak spokojną.
                theirs = returns.get(other_ex) if other_ex in survivors else 0.0
                # Przy braku historii albo remisie oznaczamy obie (nie wiemy, która ma rację).
                if mine is None or theirs is None or abs(mine) >= abs(theirs):
                    deviating.add(ex)
                    details = {"other": other_ex, "deviation": f"{dev:.6f}"}
                    result.events.append(_event(candle, CROSS_DEVIATION, "flagged", details))
                    break
        return deviating

    def _is_spike(
        self,
        candle: Candle,
        r: float | None,
        sigma: float | None,
        confirmers: Mapping[str, Candle],
        result: DqResult,
    ) -> bool:
        """Skok > 8 sigma bez potwierdzenia przez drugą giełdę (zgodną w granicy 3%)."""
        if r is None or sigma is None or abs(r) <= self.config.spike_sigmas * sigma:
            return False
        confirmed = any(
            relative_deviation(candle.close, other.close) <= self.config.max_deviation
            for other in confirmers.values()
        )
        if confirmed:
            return False
        details = {"log_return": f"{r:.6f}", "sigma": f"{sigma:.6f}"}
        result.events.append(_event(candle, PRICE_SPIKE, "flagged", details))
        return True

    def _track_level_shift(self, state: _SourceState, candle: Candle, sigma: float | None) -> None:
        """Kilka kolejnych oznaczonych świec na spójnym poziomie = nowy poziom ceny."""
        limit = self.config.spike_sigmas * (sigma or self.config.min_sigma)
        consistent = (
            state.run_close is not None
            and abs(math.log(float(candle.close / state.run_close))) <= limit
        )
        state.spike_run = state.spike_run + 1 if consistent or state.run_close is None else 1
        state.run_close = candle.close
        if state.spike_run >= self.config.level_shift_after:
            state.last_close = candle.close
            state.spike_run = 0
            state.run_close = None


def _event(
    candle: Candle,
    kind: str,
    decision: Decision,
    details: Mapping[str, str] | None = None,
) -> DqEvent:
    return DqEvent(
        exchange=candle.exchange,
        symbol=candle.symbol,
        ts_ms=candle.ts_ms,
        kind=kind,
        decision=decision,
        details=dict(details or {}),
    )
