"""Modele odpowiedzi API v1 (źródło specyfikacji OpenAPI w `packages/contracts/openapi`).

`Evidence` odpowiada kontraktowi `packages/contracts/evidence/evidence.v1.schema.json`
(test `test_openapi.py` sprawdza to na przykładach kontraktu).
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Horizon = Literal["1h", "4h", "1d", "7d"]
# Ścieżka pracy (decyzja D3, 28.11.2026): 1h z `candles_ref`, 4h i 1d z pełnych okresów 1h;
# 1m, 5m i 15m wracają w ścieżce produktu (dane minutowe nie są zbierane).
Timeframe = Literal["1h", "4h", "1d"]
DqStatus = Literal["ok", "degraded", "stale", "down"]
Regime = Literal["trend_up", "trend_down", "range", "high_volatility", "crisis"]
Symbol = Annotated[str, Field(pattern=r"^[A-Z0-9]{2,15}$", examples=["BTC"])]
Decimal = Annotated[
    str,
    Field(pattern=r"^(0|[1-9][0-9]*)(\.[0-9]+)?$", description="liczba dziesiętna jako tekst"),
]
Probability = Annotated[float, Field(ge=0, le=1)]
# Czas zawsze ze strefą (UTC w odpowiedziach); czas bez strefy jest błędem kontraktu.
Timestamp = AwareDatetime


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Problem(Model):
    """Błąd w formacie RFC 9457 (Problem Details)."""

    type: str = Field(description="URI typu błędu", examples=["about:blank"])
    title: str
    status: int = Field(ge=400, le=599)
    detail: str | None = None


class Health(Model):
    status: Literal["ok"]
    version: str


class Asset(Model):
    id: UUID
    symbol: Symbol
    name: str


class Page[T](Model):
    """Paginacja kursorowa: `next_cursor` = null na ostatniej stronie."""

    items: list[T]
    next_cursor: str | None


class Candle(Model):
    ts: Timestamp = Field(description="początek okresu świecy (UTC)")
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class OverviewItem(Model):
    """Stan aktywa w przeglądzie rynku (ostatnia świeca 1h ceny referencyjnej)."""

    asset: Asset
    ts: Timestamp = Field(description="początek ostatniej świecy 1h (UTC)")
    close: Decimal
    change_24h: float | None = Field(
        description="zmiana zamknięcia względem świecy sprzed 24 h (ułamek, 0.01 = 1%); "
        "null, gdy tamtej świecy brak"
    )
    volume_24h: Decimal | None = Field(
        description="wolumen 24 ostatnich świec 1h; null, gdy którejś brak"
    )
    dq_status: DqStatus | None = Field(
        description="najgorszy status jakości danych giełd pary; null, gdy brak oceny"
    )


class MarketOverview(Model):
    items: list[OverviewItem]


class AgentRef(Model):
    name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]


class Quantiles(Model):
    q05: float
    q25: float
    q50: float
    q75: float
    q95: float

    @model_validator(mode="after")
    def non_decreasing(self) -> "Quantiles":
        values = [self.q05, self.q25, self.q50, self.q75, self.q95]
        if values != sorted(values):
            raise ValueError("kwantyle muszą być niemalejące")
        return self


class Evidence(Model):
    """Dowód agenta (kontrakt Evidence v1)."""

    evidence_id: UUID
    schema_version: Literal[1]
    agent: AgentRef
    model_version: str | None
    asset: Symbol
    horizon: Horizon
    as_of: Timestamp
    data_cutoff: Timestamp
    p_up: Probability | None
    quantiles: Quantiles | None
    regime_view: Regime | None
    facts: dict[str, float | str | bool] = Field(min_length=1, max_length=50)
    invalidation: str = Field(min_length=1, max_length=500)
    status: Literal["active", "invalidated", "expired", "settled"]

    @model_validator(mode="after")
    def forecasts_and_point_in_time(self) -> "Evidence":
        if self.p_up is None and self.quantiles is None:
            raise ValueError("dowód musi mieć p_up albo kwantyle")
        if self.data_cutoff > self.as_of:
            raise ValueError("data_cutoff późniejsze niż as_of (zaglądanie w przyszłość)")
        return self


class Agent(Model):
    name: str
    version: str
    description: str
    horizons: list[Horizon]


class Assessment(Model):
    assessment_id: UUID
    asset: Symbol
    horizon: Horizon
    as_of: Timestamp
    p_up: Probability
    quantiles: Quantiles | None
    regime: str
    evidence_ids: list[UUID] = Field(min_length=1)
