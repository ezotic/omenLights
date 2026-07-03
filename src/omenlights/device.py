"""Low-level HID transport for the HP OMEN 'TracerLED' lighting controller.

Hardware facts established by reverse-engineering the device on an OMEN 30L:

  USB id ........ 103c:84fd  ("HP TracerLED")
  Interface ..... HID, one IN endpoint (0x81) and one OUT endpoint (0x02)
  Report ........ 57-byte, *unnumbered* (no report id) reports, both directions

Because the reports are unnumbered, the hidapi C library expects the first byte
of every write to be the report id 0x00, followed by the 57 payload bytes -- so
each ``hid_write`` call carries 58 bytes. ``send()`` handles that framing; the
rest of the package works purely in terms of the 57-byte payload.
"""

from __future__ import annotations

import hid  # provided by the `hidapi` python package (imports as `hid`)

VENDOR_ID = 0x103C
PRODUCT_ID = 0x84FD
PRODUCT_NAME = "HP TracerLED"

#: Length of the HID report payload, from the report descriptor (Report Count 0x39).
REPORT_SIZE = 57


class DeviceError(RuntimeError):
    """Raised when the controller cannot be found or opened."""


class TracerLED:
    """A thin, synchronous wrapper around the TracerLED HID interface.

    Usage::

        with TracerLED() as dev:
            dev.send(frame)   # frame is up to 57 bytes; short frames are padded
    """

    def __init__(self, vendor_id: int = VENDOR_ID, product_id: int = PRODUCT_ID):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self._dev: hid.device | None = None

    # -- lifecycle ---------------------------------------------------------
    @classmethod
    def is_present(cls, vendor_id: int = VENDOR_ID, product_id: int = PRODUCT_ID) -> bool:
        """Return True if the controller is plugged in (no open required)."""
        return any(
            d["vendor_id"] == vendor_id and d["product_id"] == product_id
            for d in hid.enumerate()
        )

    def open(self) -> "TracerLED":
        if self._dev is not None:
            return self
        if not self.is_present(self.vendor_id, self.product_id):
            raise DeviceError(
                f"{PRODUCT_NAME} ({self.vendor_id:04x}:{self.product_id:04x}) "
                "not found. Is this an OMEN with the TracerLED controller?"
            )
        dev = hid.device()
        try:
            dev.open(self.vendor_id, self.product_id)
        except (OSError, IOError) as exc:
            raise DeviceError(
                f"Cannot open {PRODUCT_NAME}: {exc}. "
                "The hidraw node is usually root-only -- install the udev rule:\n"
                "  sudo cp udev/70-omen-tracerled.rules /etc/udev/rules.d/\n"
                "  sudo udevadm control --reload && sudo udevadm trigger"
            ) from exc
        dev.set_nonblocking(False)
        self._dev = dev
        return self

    def close(self) -> None:
        if self._dev is not None:
            self._dev.close()
            self._dev = None

    def __enter__(self) -> "TracerLED":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    # -- I/O ---------------------------------------------------------------
    def send(self, payload: bytes | bytearray | list[int]) -> int:
        """Write one 57-byte report. Shorter payloads are zero-padded.

        Returns the number of bytes written by hidapi (includes the report-id
        byte). Raises DeviceError if the device is not open.
        """
        if self._dev is None:
            raise DeviceError("device not open; call open() or use a 'with' block")
        data = bytearray(payload)
        if len(data) > REPORT_SIZE:
            raise ValueError(f"frame too long: {len(data)} > {REPORT_SIZE} bytes")
        data.extend(b"\x00" * (REPORT_SIZE - len(data)))
        # Prepend report id 0x00 for the unnumbered report.
        return self._dev.write(b"\x00" + bytes(data))

    def read(self, timeout_ms: int = 200) -> bytes:
        """Read one report from the IN endpoint (best-effort; may time out)."""
        if self._dev is None:
            raise DeviceError("device not open")
        return bytes(self._dev.read(REPORT_SIZE, timeout_ms))
