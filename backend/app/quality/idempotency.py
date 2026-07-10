from __future__ import annotations

from app.core.config import settings


def create_redis_client():
    try:
        from redis import Redis
    except ImportError as exc:
        raise RuntimeError("redis is not installed") from exc
    return Redis.from_url(settings.redis_url, decode_responses=True)


def claim_event(event_id: str, *, ttl_seconds: int = 86400) -> bool:
    client = create_redis_client()
    try:
        return bool(client.set(f"idempotency:telemetry:{event_id}", "1", nx=True, ex=ttl_seconds))
    finally:
        client.close()