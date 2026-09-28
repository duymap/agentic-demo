import logging
import os
from contextvars import ContextVar

import httpx

from app.config import OMLX_API_KEY, OMLX_BASE_URL

logger = logging.getLogger(__name__)

# Attributes stamped on every span of the current request (e.g. session.id / user.id for Langfuse filtering)
_trace_attributes: ContextVar[dict[str, str]] = ContextVar("trace_attributes", default={})


def set_trace_attributes(attributes: dict[str, str]) -> None:
    _trace_attributes.set(attributes)


def setup_telemetry() -> None:
    """Enable OTLP tracing (e.g. Langfuse) only when OTEL_EXPORTER_OTLP_ENDPOINT is set."""
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        logger.info("Telemetry disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")
        return
    from agent_framework.observability import enable_instrumentation
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    class TraceAttributesProcessor(SpanProcessor):
        def on_start(self, span, parent_context=None) -> None:
            span.set_attributes(_trace_attributes.get())

    provider = TracerProvider(resource=Resource.create({"service.name": "agentic-support-demo"}))
    provider.add_span_processor(TraceAttributesProcessor())
    # Reads OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_HEADERS from the environment (OTLP over HTTP)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    enable_instrumentation()
    logger.info("Telemetry enabled -> %s", os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"])


async def check_model_server() -> None:
    """Check that oMLX is up at startup; only warn, never block the server."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.get(f"{OMLX_BASE_URL}/models", headers={"Authorization": f"Bearer {OMLX_API_KEY}"})
            res.raise_for_status()
        logger.info("Model server reachable: %s", OMLX_BASE_URL)
    except Exception as e:
        logger.warning("Cannot reach model server %s: %s", OMLX_BASE_URL, e)
