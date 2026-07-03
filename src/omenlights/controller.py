"""High-level lighting control: the API the CLI and GUI both call.

Wraps the HID transport (device.py) and the frame builder (protocol.py). The
device only understands "set zone Z to RGB", so everything else is done here:

  * brightness  -> scale each channel by percent/100 before sending (the app
                   does exactly this; there is no brightness opcode),
  * effects     -> stream frames over time (breathing, color-cycle, blink, wave).

The controller keeps the intended (unscaled) per-zone colors and the current
brightness so brightness changes can be re-applied without losing the colors.
"""

from __future__ import annotations

import colorsys
import threading
import time

from . import protocol
from .device import TracerLED
from .models import ZONES, Brightness, Color, Effect, Zone, zone_by_id


class UnverifiedProtocolError(RuntimeError):
    """Raised when attempting to send frames built from an unverified protocol."""


def scale(color: Color, percent: int) -> Color:
    """Return color with every channel scaled by percent/100 (0..100)."""
    p = max(0, min(100, percent))
    return Color(color.r * p // 100, color.g * p // 100, color.b * p // 100)


class Controller:
    def __init__(self, device: TracerLED | None = None, allow_unverified: bool = False):
        self.device = device or TracerLED()
        self.allow_unverified = allow_unverified
        self._owns_device = device is None
        self._brightness = 100
        self._colors: dict[int, Color] = {z.index: Color(0, 0, 0) for z in ZONES}

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "Controller":
        self.device.open()
        for f in protocol.init_frames():
            self.device.send(f)
        return self

    def __exit__(self, *exc) -> None:
        if self._owns_device:
            self.device.close()

    # -- transmit ----------------------------------------------------------
    def _guard(self) -> None:
        if not protocol.VERIFIED and not self.allow_unverified:
            raise UnverifiedProtocolError(
                "The TracerLED protocol is not verified. Pass allow_unverified=True "
                "/ --force to send anyway."
            )

    def _push_zone(self, zone_id: int) -> None:
        """Send the current (brightness-scaled) color for one zone."""
        color = scale(self._colors[zone_id], self._brightness)
        self.device.send(protocol.frame_set_zone(zone_id, color))

    # -- public API --------------------------------------------------------
    def zones(self) -> list[Zone]:
        return list(ZONES)

    def set_zone(self, zone: int | Zone, color: Color) -> None:
        zid = zone.index if isinstance(zone, Zone) else zone_by_id(zone).index
        self._guard()
        self._colors[zid] = color
        self._push_zone(zid)

    def set_all(self, color: Color) -> None:
        self._guard()
        for z in ZONES:
            self._colors[z.index] = color
            self._push_zone(z.index)

    def set_brightness(self, brightness: int | Brightness) -> None:
        b = brightness.percent if isinstance(brightness, Brightness) else int(brightness)
        Brightness(b)  # validate range
        self._guard()
        self._brightness = b
        for z in ZONES:
            self._push_zone(z.index)

    def off(self) -> None:
        self.set_all(Color(0, 0, 0))

    def send_raw(self, payload: bytes) -> None:
        """Escape hatch for live protocol probing."""
        self._guard()
        self.device.send(payload)

    # -- effects (host-driven; block until `stop` is set or KeyboardInterrupt) ---
    def run_effect(
        self,
        effect: Effect,
        color: Color | None = None,
        speed: int = 5,
        stop: threading.Event | None = None,
    ) -> None:
        """Run an animated effect by streaming frames until stopped.

        STATIC just applies the color once and returns. speed is 1 (slow) .. 10
        (fast). Pass a threading.Event as ``stop`` to end from another thread;
        otherwise runs until KeyboardInterrupt.
        """
        self._guard()
        base = color or Color(255, 0, 0)

        if effect == Effect.STATIC:
            self.set_all(base)
            return

        stop = stop or threading.Event()
        # frame period shrinks as speed grows
        dt = max(0.01, 0.12 - 0.011 * max(1, min(10, speed)))

        try:
            if effect == Effect.BREATHING:
                self._loop_breathing(base, dt, stop)
            elif effect == Effect.COLOR_CYCLE:
                self._loop_color_cycle(dt, stop)
            elif effect == Effect.BLINK:
                self._loop_blink(base, dt, stop)
            elif effect == Effect.WAVE:
                self._loop_wave(dt, stop)
            else:  # pragma: no cover - Effect is exhaustive
                raise ValueError(f"unhandled effect {effect}")
        except KeyboardInterrupt:
            pass

    # -- effect loops ------------------------------------------------------
    def _loop_breathing(self, base: Color, dt: float, stop: threading.Event) -> None:
        levels = list(range(0, 101, 4)) + list(range(100, -1, -4))
        while not stop.is_set():
            for lvl in levels:
                if stop.is_set():
                    break
                self.set_brightness(lvl)
                stop.wait(dt)
        # restore base at full so we don't leave it dark
        self._brightness = 100
        self.set_all(base)

    def _loop_color_cycle(self, dt: float, stop: threading.Event) -> None:
        hue = 0.0
        while not stop.is_set():
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            self.set_all(Color(int(r * 255), int(g * 255), int(b * 255)))
            hue = (hue + 0.01) % 1.0
            stop.wait(dt)

    def _loop_blink(self, base: Color, dt: float, stop: threading.Event) -> None:
        on = True
        while not stop.is_set():
            self.set_all(base if on else Color(0, 0, 0))
            on = not on
            stop.wait(dt * 4)

    def _loop_wave(self, dt: float, stop: threading.Event) -> None:
        """A hue wave that phases across the zones."""
        hue = 0.0
        n = max(1, len(ZONES))
        while not stop.is_set():
            for i, z in enumerate(ZONES):
                h = (hue + i / n) % 1.0
                r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
                self.set_zone(z, Color(int(r * 255), int(g * 255), int(b * 255)))
            hue = (hue + 0.01) % 1.0
            stop.wait(dt)
