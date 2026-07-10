from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from app.edge.contracts import EdgePointBinding, RawPointValue


def simulated_value(binding: EdgePointBinding, *, salt: str) -> RawPointValue:
    digest = hashlib.sha256(
        f"{salt}:{binding.device_code}:{binding.point_code}:{binding.source_address}".encode()
    ).hexdigest()
    ratio = int(digest[:8], 16) / 0xFFFFFFFF
    value = _scale_value(binding, ratio)
    return RawPointValue(
        binding=binding,
        value=value,
        quality=1.0 if binding.enabled else 0.0,
        acquired_at=datetime.now(UTC),
        raw_status="simulated",
        raw_payload={
            "protocol": binding.protocol,
            "source_address": binding.source_address,
            "simulation_seed": digest[:12],
        },
    )


def _scale_value(binding: EdgePointBinding, ratio: float) -> float:
    if binding.min_value is not None and binding.max_value is not None:
        return round(
            float(binding.min_value)
            + (float(binding.max_value) - float(binding.min_value)) * ratio,
            4,
        )
    return round(ratio * 100, 4)
