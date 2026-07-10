from __future__ import annotations

import logging

from app.core.config import settings
from app.quality.idempotency import create_redis_client

logger = logging.getLogger(__name__)


def should_create_warning(device_code: str, risk_type: str) -> bool:
    key = f"warning:suppress:{device_code}:{risk_type}"
    try:
        client = create_redis_client()
        try:
            return bool(client.set(key, "1", nx=True, ex=settings.warning_suppression_seconds))
        finally:
            client.close()
    except Exception as exc:
        logger.warning("Warning suppression unavailable, fail open: %s", exc)
        return True