"""Domain models shared by the protocol, controller, CLI and GUI.

These are deliberately protocol-agnostic: a Color is just an RGB triple, a Zone
is just an index+name. How they map onto the 57-byte wire frames lives entirely
in ``protocol.py``.

NOTE: the concrete zone list and effect ids are placeholders until the Windows
USB capture is decoded (see tools/PROTOCOL.md). They are structured so that
filling in real values later does not ripple into the controller/CLI/GUI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class Color:
    """An 8-bit-per-channel RGB color (channel *order on the wire* is handled by
    protocol.py -- here it is always logical R, G, B)."""

    r: int
    g: int
    b: int

    def __post_init__(self) -> None:
        for name, v in (("r", self.r), ("g", self.g), ("b", self.b)):
            if not 0 <= v <= 255:
                raise ValueError(f"channel {name}={v} out of range 0..255")

    @classmethod
    def from_hex(cls, value: str) -> "Color":
        m = _HEX_RE.match(value.strip())
        if not m:
            raise ValueError(f"invalid hex color: {value!r} (expected RRGGBB)")
        h = m.group(1)
        return cls(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    def to_hex(self) -> str:
        return f"{self.r:02x}{self.g:02x}{self.b:02x}"

    def as_tuple(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)


# A few well-known colors for convenience.
BLACK = Color(0, 0, 0)
WHITE = Color(255, 255, 255)
RED = Color(255, 0, 0)
GREEN = Color(0, 255, 0)
BLUE = Color(0, 0, 255)


@dataclass(frozen=True)
class Zone:
    """A controllable lighting zone (e.g. front logo, light bar, fans...)."""

    index: int
    name: str


# Zone map confirmed from the capture: this OMEN 30L exposes 3 zones, addressed
# by 1-based device ids (byte 53 / RGB offset 4+3*id). `index` IS the device id.
# If a machine has more zones they'd continue at ids 4, 5, ... -- extend here.
ZONES: list[Zone] = [
    Zone(1, "zone1"),
    Zone(2, "zone2"),
    Zone(3, "zone3"),
]


def zone_by_id(zone_id: int) -> Zone:
    for z in ZONES:
        if z.index == zone_id:
            return z
    raise KeyError(f"unknown zone id {zone_id}; known: {[z.index for z in ZONES]}")


class Effect(str, Enum):
    """Lighting effects. The wire id for each is resolved in protocol.py.

    Values here are stable identifiers used by the CLI/GUI/profiles; do not
    assume they equal the firmware effect ids.
    """

    STATIC = "static"
    BREATHING = "breathing"
    COLOR_CYCLE = "color_cycle"
    WAVE = "wave"
    BLINK = "blink"


@dataclass(frozen=True)
class Brightness:
    """Master brightness as a 0..100 percentage."""

    percent: int

    def __post_init__(self) -> None:
        if not 0 <= self.percent <= 100:
            raise ValueError("brightness must be 0..100")
