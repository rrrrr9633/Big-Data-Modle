from collections.abc import Mapping
from typing import Protocol

from app.edge.contracts import EdgePointBinding, RawPointValue


class CncDriverUnavailable(RuntimeError):
    pass


class CncVendorDriver(Protocol):
    def read(self, binding: EdgePointBinding) -> RawPointValue: ...


class CncAdapter:
    protocol = "cnc"

    def __init__(self, drivers: Mapping[str, CncVendorDriver] | None = None) -> None:
        self._drivers = dict(drivers or {})

    def read(self, binding: EdgePointBinding) -> RawPointValue:
        vendor = str(binding.protocol_options.get("vendor") or "").strip().lower()
        driver = self._drivers.get(vendor)
        if driver is None:
            raise CncDriverUnavailable(
                f"driver_unavailable: {vendor or 'unspecified'}; "
                "configure an approved FANUC, SINUMERIK, Mitsubishi, Haas, or Huazhong driver"
            )
        return driver.read(binding)
