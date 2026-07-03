"""Tests for models + the decoded protocol.

The frame tests assert byte-for-byte equality against real frames captured from
OMEN Light Studio (omen.pcapng) -- this is the ground truth the protocol was
reverse-engineered from.
"""

import pytest

from omenlights.device import REPORT_SIZE
from omenlights.models import Brightness, Color, Effect, Zone, ZONES, zone_by_id
from omenlights.controller import scale
from omenlights import protocol


def _hex(s: str) -> bytes:
    return bytes.fromhex(s)


def test_color_hex_roundtrip():
    c = Color.from_hex("#1a2b3c")
    assert c.as_tuple() == (0x1A, 0x2B, 0x3C)
    assert c.to_hex() == "1a2b3c"
    assert Color.from_hex("ff0000") == Color(255, 0, 0)


def test_color_validates_range():
    with pytest.raises(ValueError):
        Color(256, 0, 0)
    with pytest.raises(ValueError):
        Color.from_hex("nothex")


def test_brightness_range():
    Brightness(0)
    Brightness(100)
    with pytest.raises(ValueError):
        Brightness(101)


def test_protocol_verified():
    assert protocol.VERIFIED is True


def test_zone_map():
    assert [z.index for z in ZONES] == [1, 2, 3]
    assert zone_by_id(2).name == "zone2"
    with pytest.raises(KeyError):
        zone_by_id(9)


# --- Byte-exact frames from omen.pcapng --------------------------------------
# Pure red on each zone (capture idx 7685 / 7688 / 7691).
RED = Color(255, 0, 0)
CAP_RED_Z1 = "3b120101000000ff000000000000000000000000000000000000000000000000000000000000000000000000000000640a0000000001010000"
CAP_RED_Z2 = "3b120101000000000000ff000000000000000000000000000000000000000000000000000000000000000000000000640a0000000002010000"
CAP_RED_Z3 = "3b120101000000000000000000ff000000000000000000000000000000000000000000000000000000000000000000640a0000000003010000"
# Pure white on zone 1 (capture idx 9574).
CAP_WHITE_Z1 = "3b120101000000ffffff00000000000000000000000000000000000000000000000000000000000000000000000000640a0000000001010000"


@pytest.mark.parametrize(
    "zone_id, color, expected",
    [
        (1, RED, CAP_RED_Z1),
        (2, RED, CAP_RED_Z2),
        (3, RED, CAP_RED_Z3),
        (1, Color(255, 255, 255), CAP_WHITE_Z1),
    ],
)
def test_frame_matches_capture(zone_id, color, expected):
    frame = protocol.frame_set_zone(zone_id, color)
    assert len(frame) == REPORT_SIZE
    assert frame == _hex(expected)


def test_frame_accepts_zone_object():
    assert protocol.frame_set_zone(Zone(1, "z"), RED) == _hex(CAP_RED_Z1)


def test_brightness_scaling():
    assert scale(Color(200, 100, 50), 50) == Color(100, 50, 25)
    assert scale(Color(255, 255, 255), 0) == Color(0, 0, 0)
    assert scale(Color(10, 20, 30), 100) == Color(10, 20, 30)
