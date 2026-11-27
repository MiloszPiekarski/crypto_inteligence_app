"""Publiczny interfejs modułu features (roadmapa E5, ścieżka pracy: ADR-0008, bramka G5p)."""

from goatcash.features._impl.compute import STATUS_SUFFIX, compute_pair, status_column
from goatcash.features._impl.definitions import (
    FEATURE_NAMES,
    FEATURE_SET_NAME,
    FS_1P,
    FeatureDef,
    definition_hash,
    feature_set_definition,
    feature_set_version,
)
from goatcash.features._impl.service import (
    btc_pair,
    features_at,
    pair_frame,
    recompute_history,
    values_digest,
)
from goatcash.features._impl.types import (
    STATUSES,
    FeatureStatus,
    FeatureVector,
    Pair,
    RefBar,
    floor_hour,
)
from goatcash.features._impl.view import (
    BAR_SCHEMA,
    InMemoryRefSource,
    LookAheadError,
    MarketView,
    RefCandleSource,
)

__all__ = [
    "BAR_SCHEMA",
    "FEATURE_NAMES",
    "FEATURE_SET_NAME",
    "FS_1P",
    "STATUSES",
    "STATUS_SUFFIX",
    "FeatureDef",
    "FeatureStatus",
    "FeatureVector",
    "InMemoryRefSource",
    "LookAheadError",
    "MarketView",
    "Pair",
    "RefBar",
    "RefCandleSource",
    "btc_pair",
    "compute_pair",
    "definition_hash",
    "feature_set_definition",
    "feature_set_version",
    "features_at",
    "floor_hour",
    "pair_frame",
    "recompute_history",
    "status_column",
    "values_digest",
]
