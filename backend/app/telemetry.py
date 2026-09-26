import logging
import os

import httpx
from strands.telemetry import StrandsTelemetry

from app.config import OMLX_API_KEY, OMLX_BASE_URL

logger = logging.getLogger(__name__)


def setup_telemetry() -> None:
    """Enable OTLP tracing (e.g. Langfuse) only when OTEL_EXPORTER_OTLP_ENDPOINT is set."""
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        logger.info("Telemetry disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")
        return
    # Reads OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_HEADERS from the environment
    StrandsTelemetry().setup_otlp_exporter()
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
