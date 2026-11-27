"""Publiczny interfejs modułu features (roadmapa E5, ścieżka pracy: ADR-0008, bramka G5p)."""

from goatcash.features._impl.compute import STATUS_SUFFIX, compute_pair, status_column
from goatcash.features._impl.consumer import DEAD_LETTER, GROUP, MAX_DELIVERIES, StreamConsumer
from goatcash.features._impl.definitions import (
    FEATURE_NAMES,
    FEATURE_SET_NAME,
    FS_1P,
    FeatureDef,
    definition_hash,
    feature_set_definition,
    feature_set_version,
)
from goatcash.features._impl.job import (
    FEATURES_READY,
    FEATURES_READY_VERSION,
    FeatureJob,
    UnsupportedEventError,
    features_ready,
    vector_frame,
)
from goatcash.features._impl.pgstore import PostgresFeatureStore, PostgresRefSource
from goatcash.features._impl.service import (
    btc_pair,
    features_at,
    pair_frame,
    recompute_history,
    values_digest,
)
from goatcash.features._impl.store import (
    LONG_SCHEMA,
    FeatureSetMismatchError,
    FeatureStore,
    InMemoryFeatureStore,
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
    "DEAD_LETTER",
    "FEATURES_READY",
    "FEATURES_READY_VERSION",
    "FEATURE_NAMES",
    "FEATURE_SET_NAME",
    "FS_1P",
    "GROUP",
    "LONG_SCHEMA",
    "MAX_DELIVERIES",
    "STATUSES",
    "STATUS_SUFFIX",
    "FeatureDef",
    "FeatureJob",
    "FeatureSetMismatchError",
    "FeatureStatus",
    "FeatureStore",
    "FeatureVector",
    "InMemoryFeatureStore",
    "InMemoryRefSource",
    "LookAheadError",
    "MarketView",
    "Pair",
    "PostgresFeatureStore",
    "PostgresRefSource",
    "RefBar",
    "RefCandleSource",
    "StreamConsumer",
    "UnsupportedEventError",
    "btc_pair",
    "compute_pair",
    "definition_hash",
    "feature_set_definition",
    "feature_set_version",
    "features_at",
    "features_ready",
    "floor_hour",
    "pair_frame",
    "recompute_history",
    "status_column",
    "values_digest",
    "vector_frame",
]
