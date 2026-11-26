"""Ślady OpenTelemetry procesu api (roadmapa E3, zakres 6: OTel → Grafana Cloud, śledzenie).

Eksport włącza zmienna OTEL_EXPORTER_OTLP_ENDPOINT (Compose staging: kolektor OTel, który
wysyła ślady do Grafana Cloud Tempo); bez niej (testy, praca lokalna) aplikacja nie wysyła
niczego. Nazwę usługi daje OTEL_SERVICE_NAME, wersję pakiet `goatcash`.
"""

import os

from fastapi import FastAPI
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from goatcash.common.api import package_version


def setup_tracing(app: FastAPI, processor: SpanProcessor | None = None) -> bool:
    """Instrumentuje aplikację; zwraca False, gdy eksport jest wyłączony.

    `processor` podają testy (eksport do pamięci); domyślnie eksport OTLP/HTTP partiami.
    """
    if processor is None:
        if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            return False
        processor = BatchSpanProcessor(OTLPSpanExporter())
    provider = TracerProvider(resource=Resource.create({SERVICE_VERSION: package_version()}))
    provider.add_span_processor(processor)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    return True
