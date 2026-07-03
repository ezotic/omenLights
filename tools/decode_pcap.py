#!/usr/bin/env python3
"""Extract and diff the OUT HID frames sent to the HP TracerLED (103c:84fd).

This is the reverse-engineering workbench. Point it at a USBPcap .pcapng recorded
on Windows while driving OMEN Light Studio (see CAPTURE_GUIDE.md). It uses
`tshark` (install `wireshark-cli` on Arch) to pull every host->device interrupt
transfer to the controller, prints each 57-byte payload, and highlights the bytes
that changed since the previous frame -- which is how we recover the layout.

Usage:
    tools/decode_pcap.py capture.pcapng                 # auto-detect device
    tools/decode_pcap.py capture.pcapng --address 7     # force USB address
    tools/decode_pcap.py capture.pcapng --list-devices  # list candidates
    tools/decode_pcap.py capture.pcapng --unique        # collapse repeats

Requires: tshark on PATH.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections import Counter

VENDOR = "0x103c"
PRODUCT = "0x84fd"

# ANSI for highlighting changed bytes.
_RED = "\033[31m"
_DIM = "\033[2m"
_RST = "\033[0m"


def _need_tshark() -> str:
    path = shutil.which("tshark")
    if not path:
        sys.exit(
            "tshark not found. Install it:\n"
            "  sudo pacman -S wireshark-cli\n"
            "(then re-run this script)."
        )
    return path


def _tshark(pcap: str, display_filter: str, fields: list[str]) -> list[list[str]]:
    cmd = [_need_tshark(), "-r", pcap, "-Y", display_filter, "-T", "fields"]
    for f in fields:
        cmd += ["-e", f]
    cmd += ["-E", "separator=\t", "-E", "occurrence=f"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"tshark failed:\n{out.stderr}")
    rows = []
    for line in out.stdout.splitlines():
        if line.strip():
            rows.append(line.split("\t"))
    return rows


def detect_address(pcap: str) -> str | None:
    """Find the USB device address whose descriptor advertises 84fd."""
    rows = _tshark(
        pcap,
        f"usb.idVendor == {VENDOR} && usb.idProduct == {PRODUCT}",
        ["usb.device_address"],
    )
    addrs = [r[0] for r in rows if r and r[0]]
    if addrs:
        return Counter(addrs).most_common(1)[0][0]
    return None


def list_devices(pcap: str) -> None:
    """Show device addresses that emitted OUT interrupt data, to pick from."""
    rows = _tshark(
        pcap,
        "usb.transfer_type == 0x01 && usb.endpoint_address.direction == 0 && usb.capdata",
        ["usb.device_address", "usb.capdata"],
    )
    counts: Counter = Counter()
    sample: dict[str, str] = {}
    for r in rows:
        if len(r) >= 1 and r[0]:
            counts[r[0]] += 1
            if len(r) >= 2 and r[0] not in sample:
                sample[r[0]] = r[1]
    if not counts:
        print("No OUT interrupt data frames found at all.")
        return
    print("USB addr | OUT frames | first payload")
    print("---------+------------+--------------")
    for addr, n in counts.most_common():
        print(f"{addr:>8} | {n:>10} | {sample.get(addr,'')[:48]}")
    print("\nRe-run with --address <addr> for the TracerLED.")


def _payload_bytes(hexstr: str) -> bytes:
    return bytes.fromhex(hexstr.replace(":", "").replace(" ", ""))


def _fmt(frame: bytes, prev: bytes | None, width: int = 57) -> str:
    parts = []
    for i in range(width):
        b = frame[i] if i < len(frame) else 0
        cell = f"{b:02x}"
        if prev is not None:
            pb = prev[i] if i < len(prev) else 0
            if b != pb:
                cell = f"{_RED}{cell}{_RST}"
            elif b == 0:
                cell = f"{_DIM}{cell}{_RST}"
        parts.append(cell)
    return " ".join(parts)


def dump(pcap: str, address: str, unique: bool) -> None:
    rows = _tshark(
        pcap,
        (
            f"usb.device_address == {address} && usb.transfer_type == 0x01 "
            "&& usb.endpoint_address.direction == 0 "
            "&& (usb.capdata || usbhid.data)"
        ),
        ["frame.number", "frame.time_relative", "usb.capdata", "usbhid.data"],
    )
    if not rows:
        print(f"No OUT frames for device address {address}. Try --list-devices.")
        return

    print(f"Decoded {len(rows)} OUT frames to device address {address}.")
    print("Legend: red = changed vs previous frame, dim = zero byte.\n")
    print("  idx  time      bytes[0..56]")
    prev: bytes | None = None
    shown = 0
    last_hex = None
    for r in rows:
        num = r[0] if len(r) > 0 else "?"
        t = r[1] if len(r) > 1 else ""
        raw = (r[2] if len(r) > 2 and r[2] else "") or (r[3] if len(r) > 3 else "")
        if not raw:
            continue
        if unique and raw == last_hex:
            continue
        last_hex = raw
        frame = _payload_bytes(raw)
        try:
            tval = f"{float(t):8.3f}"
        except ValueError:
            tval = f"{t:>8}"
        print(f"{int(num):>5} {tval}  {_fmt(frame, prev)}")
        prev = frame
        shown += 1
    print(f"\nShown {shown} frames.")
    print(
        "Next: correlate timestamps with your capture step log, then encode the "
        "layout in tools/PROTOCOL.md and src/omenlights/protocol.py."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pcap", help="path to the .pcapng capture")
    ap.add_argument("--address", help="USB device address of the TracerLED")
    ap.add_argument("--list-devices", action="store_true", help="list candidate devices and exit")
    ap.add_argument("--unique", action="store_true", help="collapse consecutive identical frames")
    args = ap.parse_args()

    if args.list_devices:
        list_devices(args.pcap)
        return

    address = args.address or detect_address(args.pcap)
    if not address:
        print(
            "Could not auto-detect the TracerLED address (no descriptor packet in "
            "the capture -- the device was likely already enumerated before capture "
            "started).\n"
        )
        list_devices(args.pcap)
        return

    dump(args.pcap, address, args.unique)


if __name__ == "__main__":
    main()
