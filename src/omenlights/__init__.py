"""OmenLights -- control HP OMEN 'TracerLED' (103c:84fd) RGB lighting on Linux."""

from .controller import Controller, UnverifiedProtocolError
from .device import TracerLED, DeviceError
from .models import Brightness, Color, Effect, Zone, ZONES

__version__ = "0.1.0"

__all__ = [
    "Controller",
    "UnverifiedProtocolError",
    "TracerLED",
    "DeviceError",
    "Brightness",
    "Color",
    "Effect",
    "Zone",
    "ZONES",
]
