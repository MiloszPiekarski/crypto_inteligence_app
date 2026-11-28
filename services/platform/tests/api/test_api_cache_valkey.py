"""Cache API na prawdziwym Valkey (E6, bramka G6p, `api-db`, marker `db`).

- słuchacz w osobnym wątku (jak w procesie api) czyta `ev:candle.closed` przez XREAD;
  zdarzenie publikuje prawdziwy przekaźnik outbox z marketdata (ta sama koperta co ingest)
  i unieważnia odpowiedź tego aktywa w czasie dostarczenia;
- dwie instancje api na jednym Valkey: każda dostaje każde zdarzenie (XREAD bez grupy);
- Valkey niedostępny (zły adres): odpowiedzi prosto z bazy, szybko i bez błędów.
Uruchomienie: `make api-db-test` (Docker). Lokalnie bez Dockera: `GOATCASH_TEST_VALKEY_URL`.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import pytest
import redis
from api_data import reader
from fastapi.testclient import TestClient
from httpx import Response
from redis.exceptions import ConnectionError as ValkeyDown
from testcontainers.community.redis import RedisContainer

from goatcash.http_api import cache
from goatcash.http_api.app import create_app
from goatcash.marketdata.api import (
    CANDLE_STREAM,
    Candle,
    OutboxEvent,
    asset_public_id,
    candle_closed,
    relay_outbox,
)

pytestmark = pytest.mark.db

VALKEY_IMAGE = (
    "valkey/valkey:9.0.8-alpine"
    "@sha256:139d21c97b1a956e42e29b1e4ede4752a6ff52d1a0db9ef0ff4954a570f23976"
)


@pytest.fixture(scope="module")
def valkey_url() -> Iterator[str]:
    if url := os.environ.get("GOATCASH_TEST_VALKEY_URL"):
        yield url
        return
    with RedisContainer(VALKEY_IMAGE) as container:
        host = container.get_container_host_ip()
        yield f"redis://{host}:{container.get_exposed_port(6379)}/0"


class OneEvent:
    """Magazyn outbox z jednym zdarzeniem (przekaźnik publikuje je jak w procesie ingest)."""

    def __init__(self, event: OutboxEvent) -> None:
        self.rows = [(1, event)]

    def unpublished(self, limit: int, types: Sequence[str] | None = None) -> Any:
        rows, self.rows = self.rows, []
        return rows

    def mark_published(self, outbox_ids: Sequence[int], published_at: datetime) -> None:
        return None


def publish(client: redis.Redis, base: str) -> None:
    candle = Candle(
        exchange="okx",
        symbol=f"{base}-USDT",
        timeframe="1h",
        ts_ms=1_767_225_600_000,
        open=Decimal(1),
        high=Decimal(1),
        low=Decimal(1),
        close=Decimal(1),
        volume=Decimal(1),
    )
    event = candle_closed(candle, 1, source="okx-rest")
    relay_outbox(OneEvent(event), cast(Any, client), producer="ingest@test", now=datetime.now(UTC))


def instance(url: str) -> tuple[TestClient, cache.Invalidator]:
    plain = cast(cache.Valkey, redis.Redis.from_url(url, socket_timeout=0.25))  # pyright: ignore[reportUnknownMemberType]
    listener = cast(cache.Valkey, redis.Redis.from_url(url, socket_timeout=10))  # pyright: ignore[reportUnknownMemberType]
    inv = cache.Invalidator(listener)
    return TestClient(create_app(reader(), valkey=plain, invalidator=inv)), inv


def get(client: TestClient, url: str) -> Response:
    return cast(Response, client.get(url))  # pyright: ignore[reportUnknownMemberType]


def wait_for(predicate: Any, timeout: float = 10.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_xread_invalidates_on_every_instance(valkey_url: str) -> None:
    raw = redis.Redis.from_url(valkey_url)  # pyright: ignore[reportUnknownMemberType]
    raw.flushall()  # pyright: ignore[reportUnknownMemberType]
    a, inv_a = instance(valkey_url)
    b, inv_b = instance(valkey_url)
    for inv in (inv_a, inv_b):
        inv.start()
    try:
        assert wait_for(lambda: inv_a.healthy() and inv_b.healthy())
        btc = f"/v1/assets/{asset_public_id('BTC')}/candles?timeframe=1h&limit=2"
        eth = f"/v1/assets/{asset_public_id('ETH')}/candles?timeframe=1h&limit=2"
        for client in (a, b):
            get(client, btc)
            get(client, eth)
        assert get(a, btc).headers["cache-status"] == "goatcash; hit"
        publish(raw, "BTC")
        assert raw.xlen(CANDLE_STREAM) >= 1  # pyright: ignore[reportUnknownMemberType]
        # obie instancje (każda swoim słuchaczem) widzą unieważnienie
        assert wait_for(lambda: get(a, btc).headers["cache-status"] != "goatcash; hit")
        get(b, btc)
        assert get(b, btc).headers["cache-status"] == "goatcash; hit"  # nowy wpis
        assert get(a, eth).headers["cache-status"] == "goatcash; hit"  # inne aktywo bez zmian
    finally:
        inv_a.stop()
        inv_b.stop()


def test_unreachable_valkey_bypasses_quickly() -> None:
    url = "redis://127.0.0.1:1/0"  # nic tam nie nasłuchuje
    raw = redis.Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
        url, socket_timeout=0.25, socket_connect_timeout=0.25
    )
    plain = cast(cache.Valkey, raw)
    inv = cache.Invalidator(plain)
    client = TestClient(create_app(reader(), valkey=plain, invalidator=inv))
    with pytest.raises(ValkeyDown):
        inv.poll(block_ms=0)
    started = time.monotonic()
    response = get(client, "/v1/market/overview")
    assert response.status_code == 200
    assert response.headers["cache-status"] == "goatcash; fwd=bypass"
    assert time.monotonic() - started < 1.0
