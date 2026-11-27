# pyright: reportMissingTypeStubs=false
"""Sonda dostępu do giełd (`python -m goatcash.marketdata probe`): wynik, kod wyjścia, archiwum."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any, cast

import ccxt
from md_helpers import replay_source

from goatcash.marketdata._impl.cassette import Interaction, ReplaySession
from goatcash.marketdata._impl.probe import ARCHIVE_BEGIN, ARCHIVE_END, run_probe
from goatcash.marketdata.api import BybitSource, RetryPolicy, load_universe

UNIVERSE = load_universe()
CLOUDFRONT_403 = Interaction(
    "GET",
    "",
    403,
    '{"error":"The Amazon CloudFront distribution is configured to block access '
    'from your country"}',
)


def okx_source() -> Any:
    source, _ = replay_source("okx", [f"candles_{s}" for s in UNIVERSE.symbols])
    return source


def blocked_bybit() -> Any:
    # Bybit z sesji asystenta (26.11.2026): 403 CloudFront na każde zapytanie. Ta sama
    # odpowiedź przez prawdziwy ccxt bybit (sesja odtwarzająca z podmianą odpowiedzi).
    client = ccxt.bybit(
        {"enableRateLimit": False, "options": {"fetchMarkets": {"types": ["spot"]}}}
    )

    def blocked(method: str, url: str, n: int) -> Interaction:
        return CLOUDFRONT_403

    cast(Any, client).session = ReplaySession([], override=blocked)
    return BybitSource(client, retry=RetryPolicy(max_attempts=2, sleep=lambda _: None))


def run(sources: dict[str, Any], **kwargs: Any) -> tuple[int, list[str]]:
    lines: list[str] = []
    code = run_probe(UNIVERSE, sources=sources, out=lines.append, **kwargs)
    return code, lines


def results(lines: list[str]) -> dict[str, dict[str, Any]]:
    found = [
        json.loads(line.removeprefix("SONDA ")) for line in lines if line.startswith("SONDA {")
    ]
    return {r["exchange"]: r for r in found}


def test_blocked_exchange_fails_probe_and_skips_recording() -> None:
    recorded: list[str] = []

    def recorder(exchange: str, _: object, __: Path) -> None:
        recorded.append(exchange)

    code, lines = run(
        {"okx": okx_source(), "bybit": blocked_bybit()},
        record_exchange="bybit",
        recorder=recorder,
    )
    assert code == 1
    r = results(lines)
    assert r["okx"]["ok"] is True
    assert r["okx"]["pairs_available"] == 20
    assert set(r["okx"]["first_candle"].values()) == {"2023-01-01T00:00:00+00:00"}
    assert r["bybit"]["reachable"] is False
    assert "403" in r["bybit"]["error"] or "CloudFront" in r["bybit"]["error"]
    assert "SONDA WYNIK: BLOKADA albo BŁĄD" in lines
    assert recorded == []  # bez dostępu nie nagrywamy


def test_success_records_and_prints_verifiable_archive(tmp_path: Path) -> None:
    def recorder(exchange: str, _: object, out_dir: Path) -> None:
        target = out_dir / exchange
        target.mkdir(parents=True)
        (target / "instruments.json").write_text('{"x": 1}\n', encoding="utf-8")
        (target / "candles_BTC-USDT.json").write_text('{"y": 2}\n', encoding="utf-8")

    code, lines = run(
        {"okx": okx_source(), "bybit": okx_source()}, record_exchange="bybit", recorder=recorder
    )
    # Atrapa: „bybit” to tu źródło OKX (wynik sondy dotyczy dostępności, nie nazwy giełdy).
    assert code == 0
    begin = next(i for i, line in enumerate(lines) if line.startswith(ARCHIVE_BEGIN))
    end = lines.index(ARCHIVE_END)
    digest = lines[begin].split("sha256=")[1].split()[0]
    data = base64.decodebytes("\n".join(lines[begin + 1 : end]).encode("ascii"))
    assert hashlib.sha256(data).hexdigest() == digest
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        assert sorted(tar.getnames()) == ["bybit/candles_BTC-USDT.json", "bybit/instruments.json"]


def test_probe_without_record_returns_zero_when_both_ok() -> None:
    code, lines = run({"okx": okx_source(), "bybit": okx_source()})
    assert code == 0
    assert not any(line.startswith(ARCHIVE_BEGIN) for line in lines)
