"""Nagłówki bezpieczeństwa i CORS (roadmapa E6, punkt 1; bramka G6p).

- Nagłówki dostaje **każda** odpowiedź: 2xx, błędy RFC 9457, odpowiedzi CORS (także
  odrzucone zapytania wstępne) i 500 z nieobsłużonego wyjątku. Dlatego middleware jest
  zewnętrzną warstwą i sam zamienia nieobsłużony wyjątek na 500 w formacie RFC 9457
  (domyślny `ServerErrorMiddleware` Starlette leży poza middleware aplikacji i zwróciłby
  odpowiedź bez nagłówków).
- API zwraca tylko JSON, więc CSP blokuje wszystko (`default-src 'none'`); strony
  dokumentacji (Swagger UI, ReDoc) są wyłączone, specyfikacja jest pod `/openapi.json`.
- CORS: tylko `https://app.goatcash.app`, tylko odczyt (GET), bez ciasteczek
  (w ścieżce pracy nie ma kont).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from goatcash.http_api.errors import problem

APP_ORIGIN = "https://app.goatcash.app"
SECURITY_HEADERS: dict[str, str] = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cross-Origin-Resource-Policy": "same-site",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
log = logging.getLogger("goatcash.api")


class SecurityHeaders:
    """Czysty middleware ASGI: dopisuje nagłówki do startu każdej odpowiedzi HTTP."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._raw = [(k.lower().encode(), v.encode()) for k, v in SECURITY_HEADERS.items()]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_with_headers(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                names = {k for k, _ in self._raw}
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in names]
                message["headers"] = headers + self._raw
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            log.exception("nieobsłużony wyjątek w api")
            if started:
                raise
            await problem(500)(scope, receive, send_with_headers)


def install(app: FastAPI) -> None:
    # Kolejność: ostatni dodany jest zewnętrzny, więc nagłówki obejmują też odpowiedzi CORS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[APP_ORIGIN],
        allow_methods=["GET"],
        allow_headers=[],
        allow_credentials=False,
        max_age=600,
    )
    app.add_middleware(SecurityHeaders)
