"""Wire protocol for the TracerLED controller: model objects -> 57-byte frames.

VERIFIED against a USBPcap capture of OMEN Light Studio on an OMEN 30L
(see tools/PROTOCOL.md). The controller speaks a single command -- "set zone Z
to RGB" -- as a 57-byte frame:

    off  0  1  2  3   ...   4+3*Z .. +2   ...   47 48   53    54
        3b 12 01 01        [ R  G  B ]         64 0a    Z     01

with everything else zero. Brightness and animated effects are done host-side by
scaling/streaming these frames (the app does the same); there is no separate
opcode for them.
"""

from __future__ import annotations

from .device import REPORT_SIZE
from .models import Color, Zone

#: The protocol is confirmed from a real capture.
VERIFIED = True

# Constant header (bytes 0..3) present in every frame.
_HEADER = (0x3B, 0x12, 0x01, 0x01)

# Constant tail fields observed in every frame.
_BYTE47 = 0x64  # constant (100) -- likely a global brightness left at max
_BYTE48 = 0x0A  # constant (10)  -- unknown param
_BYTE54 = 0x01  # constant

#: RGB triple for zone z starts at this byte offset.
def color_offset(zone_id: int) -> int:
    return 4 + 3 * zone_id


def frame_set_zone(zone: Zone | int, color: Color) -> bytes:
    """Build the 57-byte frame that sets one zone to a solid RGB color.

    ``zone`` may be a Zone or a 1-based device zone id.
    """
    zid = zone.index if isinstance(zone, Zone) else int(zone)
    f = bytearray(REPORT_SIZE)
    f[0:4] = bytes(_HEADER)
    off = color_offset(zid)
    if off + 3 > REPORT_SIZE:
        raise ValueError(f"zone id {zid} out of range for a {REPORT_SIZE}-byte report")
    f[off] = color.r
    f[off + 1] = color.g
    f[off + 2] = color.b
    f[47] = _BYTE47
    f[48] = _BYTE48
    f[53] = zid
    f[54] = _BYTE54
    return bytes(f)


def init_frames() -> list[bytes]:
    """No handshake/init frames are required (none seen in the capture)."""
    return []


def commit_frames() -> list[bytes]:
    """No separate commit frame is required (the app sends none)."""
    return []
