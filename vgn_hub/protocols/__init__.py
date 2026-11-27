"""Protocol factory for VGN devices."""

from __future__ import annotations

from ..transport import FeatureTransport, HidDeviceInfo
from .ry_mouse import ProtocolError, RyMouseClient


def create_client(
    transport: FeatureTransport, device_info: HidDeviceInfo | None = None
) -> RyMouseClient:
    """Instantiate the protocol client matching a discovered device's protocol_family."""
    info = device_info or transport.info
    family = info.spec.protocol_family if (info and info.spec) else "vgn-ry-mouse"
    if family == "vgn-ry-mouse":
        return RyMouseClient(transport, info)
    raise ProtocolError(f"Unsupported protocol family: {family}")


__all__ = ["ProtocolError", "RyMouseClient", "create_client"]
