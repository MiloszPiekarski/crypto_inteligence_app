"""Ślady OTel procesu api (E3): bez OTEL_EXPORTER_OTLP_ENDPOINT nic nie jest wysyłane,
z nim każde zapytanie HTTP daje span z nazwą trasy i nazwą usługi z OTEL_SERVICE_NAME."""

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from goatcash.http_api.app import create_app
from goatcash.http_api.telemetry import setup_tracing


def get(client: TestClient, url: str) -> Response:
    return client.get(url)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


def test_tracing_disabled_without_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert setup_tracing(create_app()) is False


def test_request_produces_span(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_SERVICE_NAME", "goatcash-api")
    exporter = InMemorySpanExporter()
    app = create_app()
    assert setup_tracing(app, SimpleSpanProcessor(exporter)) is True
    response = get(TestClient(app), "/v1/health")
    assert response.status_code == 200
    server = [s for s in exporter.get_finished_spans() if s.kind.name == "SERVER"]
    assert [s.name for s in server] == ["GET /v1/health"]
    resource = server[0].resource.attributes
    assert resource["service.name"] == "goatcash-api"
    assert resource["service.version"] == "0.1.0"
    attributes = server[0].attributes
    assert attributes is not None
    # Nazwa atrybutu zależy od wersji konwencji semantycznych (stara albo nowa).
    assert attributes.get("http.status_code", attributes.get("http.response.status_code")) == 200
