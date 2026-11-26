"""Nagrywanie i odtwarzanie odpowiedzi HTTP giełd (kasety) na poziomie sesji `requests` ccxt.

Nagranie: prawdziwa sesja `requests` owinięta tak, że każda odpowiedź (metoda, URL, status,
surowa treść) trafia do kasety. Odtworzenie: sesja zastępcza zwraca nagraną odpowiedź dla
tego samego żądania, więc cała ścieżka ccxt (budowa URL, parsowanie JSON, mapowanie
błędów HTTP, np. 429 → `RateLimitExceeded`) działa jak na żywo, bez sieci.

Kaseta to JSON: {"exchange", "recorded_at", "note", "interactions": [{"method", "url",
"status", "body"}]}. Treść odpowiedzi jest zapisana dosłownie; wyjątek opisany w `note`
(lista instrumentów przycięta do par z uniwersum, bo pełna ma ponad 1 MB).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast

import requests
from requests.cookies import RequestsCookieJar


@dataclass(slots=True)
class Interaction:
    method: str
    url: str
    status: int
    body: str


@dataclass(slots=True)
class Cassette:
    exchange: str
    recorded_at: str
    note: str = ""
    interactions: list[Interaction] = field(default_factory=list[Interaction])

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "exchange": self.exchange,
            "recorded_at": self.recorded_at,
            "note": self.note,
            "interactions": [
                {"method": i.method, "url": i.url, "status": i.status, "body": i.body}
                for i in self.interactions
            ],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Cassette:
        raw = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        return cls(
            exchange=str(raw["exchange"]),
            recorded_at=str(raw["recorded_at"]),
            note=str(raw.get("note", "")),
            interactions=[
                Interaction(str(i["method"]), str(i["url"]), int(i["status"]), str(i["body"]))
                for i in cast(list[dict[str, Any]], raw["interactions"])
            ],
        )


def _response(method: str, url: str, status: int, body: str) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response.reason = HTTPStatus(status).phrase
    response.url = url
    response._content = body.encode("utf-8")  # pyright: ignore[reportPrivateUsage]
    response.headers["Content-Type"] = "application/json"
    response.request = requests.Request(method, url).prepare()
    return response


class ReplaySession:
    """Sesja zastępcza dla ccxt: odpowiedzi z kaset, kolejne nagrania tego samego URL po kolei.

    `override` pozwala podmienić odpowiedź (np. 429 przed właściwą) w testach odporności.
    Żądanie bez nagrania to błąd testu (`KeyError`), a nie cicha pusta odpowiedź.
    """

    def __init__(
        self,
        cassettes: list[Cassette],
        override: Callable[[str, str, int], Interaction | None] | None = None,
    ) -> None:
        self._queue: dict[tuple[str, str], list[Interaction]] = {}
        for cassette in cassettes:
            for i in cassette.interactions:
                self._queue.setdefault((i.method, i.url), []).append(i)
        self._served: dict[tuple[str, str], int] = {}
        self._override = override
        self.requests: list[tuple[str, str]] = []
        self.cookies = RequestsCookieJar()
        self.headers: dict[str, str] = {}

    def request(self, method: str, url: str, **_: object) -> requests.Response:
        key = (method, url)
        self.requests.append(key)
        if self._override is not None:
            replaced = self._override(method, url, len(self.requests))
            if replaced is not None:
                return _response(method, url, replaced.status, replaced.body)
        recorded = self._queue.get(key)
        if not recorded:
            raise KeyError(f"brak nagrania dla {method} {url}")
        index = self._served.get(key, 0)
        self._served[key] = index + 1
        item = recorded[min(index, len(recorded) - 1)]
        return _response(method, url, item.status, item.body)


class RecordingSession:
    """Prawdziwa sesja `requests` (zmienne proxy ze środowiska), zapis każdej odpowiedzi."""

    def __init__(self, cassette: Cassette, session: requests.Session | None = None) -> None:
        self.cassette = cassette
        self._session = session or requests.Session()
        self._session.trust_env = True
        self.cookies = self._session.cookies
        self.headers = self._session.headers

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.pop("proxies", None)  # ccxt podaje puste proxies; bierzemy je ze środowiska
        response = self._session.request(method, url, **kwargs)
        response.encoding = "utf-8"
        self.cassette.interactions.append(
            Interaction(method, url, response.status_code, response.text)
        )
        return response


def now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
