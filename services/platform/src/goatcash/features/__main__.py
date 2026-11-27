"""`python -m goatcash.features <polecenie>`: zadania modułu features (roadmapa E5).

- `worker`: proces liczenia cech po `candle.closed` (grupa `features` na `ev:candle.closed`)
  i publikacja własnych `features.ready` z outbox; zmienne `GOATCASH_DATABASE_URL`
  i `GOATCASH_VALKEY_URL`. Na staging od E7 (decyzja właściciela 27.11.2026, karta E5).
- `recompute [--until ISO]`: pełne przeliczenie historii cech i zapis (zadanie wsadowe).
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
from datetime import UTC, datetime
from typing import Any

import psycopg


def _connect(url: str) -> psycopg.Connection[Any]:
    """Połączenie z adresu SQLAlchemy z rolą procesu `goatcash_app` (uprawnienia z migracji)."""
    conn = psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"), autocommit=True)
    conn.execute("SET ROLE goatcash_app")
    return conn


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"brak zmiennej środowiska {name}")
    return value


def worker_main() -> int:
    import redis  # noqa: PLC0415 (klient potrzebny tylko w procesie worker)

    from goatcash.common.api import package_version  # noqa: PLC0415
    from goatcash.features._impl.consumer import StreamConsumer  # noqa: PLC0415
    from goatcash.features._impl.job import FEATURES_READY, FeatureJob  # noqa: PLC0415
    from goatcash.features._impl.pgstore import (  # noqa: PLC0415
        PostgresFeatureStore,
        PostgresRefSource,
    )
    from goatcash.marketdata.api import PostgresStore, relay_outbox  # noqa: PLC0415

    version = package_version()
    producer = f"worker@{version}"
    url = _env("GOATCASH_DATABASE_URL")
    job = FeatureJob(
        PostgresFeatureStore(_connect(url)), PostgresRefSource(_connect(url)), code_version=version
    )
    outbox = PostgresStore(_connect(url))
    client = redis.Redis.from_url(_env("GOATCASH_VALKEY_URL"), decode_responses=True)  # pyright: ignore[reportUnknownMemberType]
    consumer = StreamConsumer(client, job.on_candle_closed, consumer=socket.gethostname())  # pyright: ignore[reportArgumentType]
    stop = {"now": False}

    def on_signal(*_: object) -> None:
        stop["now"] = True

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    print(f"worker: start {producer}, fs-1p {job.version}")
    consumer.run(
        lambda: stop["now"],
        after_step=[
            lambda: relay_outbox(outbox, client, producer=producer, types=(FEATURES_READY,))  # pyright: ignore[reportArgumentType]
        ],
    )
    return 0


def recompute_main(until: str | None) -> int:
    from goatcash.common.api import package_version  # noqa: PLC0415
    from goatcash.features._impl.job import FeatureJob  # noqa: PLC0415
    from goatcash.features._impl.pgstore import (  # noqa: PLC0415
        PostgresFeatureStore,
        PostgresRefSource,
    )

    moment = datetime.now(tz=UTC) if until is None else datetime.fromisoformat(until)
    if moment.tzinfo is None:
        raise SystemExit("--until wymaga strefy czasowej (np. 2026-11-27T10:00:00Z)")
    url = _env("GOATCASH_DATABASE_URL")
    job = FeatureJob(
        PostgresFeatureStore(_connect(url)),
        PostgresRefSource(_connect(url)),
        code_version=package_version(),
    )
    changed = job.recompute(round(moment.timestamp() * 1000))
    print(f"recompute: fs-1p {job.version}, zmienionych chwil: {changed}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m goatcash.features")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("worker", help="liczenie cech po candle.closed (Valkey + Postgres)")
    rec = sub.add_parser("recompute", help="pełne przeliczenie historii cech")
    rec.add_argument("--until", help="koniec przeliczenia (ISO 8601 ze strefą); domyślnie teraz")
    args = parser.parse_args(argv)
    if args.command == "worker":
        return worker_main()
    return recompute_main(args.until)


if __name__ == "__main__":
    raise SystemExit(main())
