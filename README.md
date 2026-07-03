# OmenLights

OmenLights is ArchLinux clone of **HP OMEN Light Studio** for controlling the RGB lighting on
HP OMEN desktops (built and tested against an **OMEN 30L GT13**).

HP ships Light Studio only for Windows. On these desktops the lighting is **not**
on the `hp-wmi` kernel path (that only exposes fans/sensors here) — it's a USB
HID device, **`103c:84fd` "HP TracerLED"**, the same one Light Studio drives.
OmenLights talks to it directly.

> ⚠️ **Status: reverse-engineering in progress.** The 57-byte HID *transport* is
> fully known, but the *meaning* of the payload bytes is still being recovered
> from a Windows USB capture. Until that's done, `protocol.VERIFIED` is `False`
> and the tools refuse to send guessed frames to your hardware unless you force
> it. See [tools/CAPTURE_GUIDE.md](tools/CAPTURE_GUIDE.md).

## What works today

- Device detection and a complete HID transport layer (`device.py`).
- A control library, CLI, and PySide6 GUI — all functional, gated behind the
  protocol-verification safety check.
- A reverse-engineering workbench (`tools/decode_pcap.py`) to decode a capture.

## Install

```bash
# system dependency: the hidapi C library (already present on this machine)
sudo pacman -S --needed hidapi          # Arch
# for decoding captures:
sudo pacman -S --needed wireshark-cli    # provides tshark

# python package (editable)
pip install -e .          # core (CLI)
pip install -e '.[gui]'   # + PySide6 GUI
pip install -e '.[dev]'   # + pytest
```

### Device access (no root)

`/dev/hidraw0` is root-only by default. Install the udev rule once:

```bash
sudo cp udev/70-omen-tracerled.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
```

## Usage

```bash
omenlights info                 # device present? protocol verified?
omenlights list-zones
omenlights zone 0 ff0000        # zone 0 -> red   (needs --force until verified)
omenlights all 00ff00
omenlights brightness 80
omenlights effect wave --color 0000ff --speed 5
omenlights --force probe 00 01 00 ff 00 00   # raw frame, for protocol probing
omenlights-gui                  # graphical app
```

Until the protocol is verified, hardware-touching commands print a warning and
exit unless you pass `--force` (CLI) or tick "Send to hardware" (GUI).

## Finishing the reverse-engineering

1. Boot Windows, follow [tools/CAPTURE_GUIDE.md](tools/CAPTURE_GUIDE.md) to record
   a scripted USB capture of Light Studio.
2. Back on Linux: `tools/decode_pcap.py tools/captures/omen-capture.pcapng`
3. Encode the byte layout in [tools/PROTOCOL.md](tools/PROTOCOL.md) and
   `src/omenlights/protocol.py`, then flip `VERIFIED = True`.
4. `pytest` (frame tests) and verify live: `omenlights all ff0000`.

## Project layout

```
src/omenlights/
  device.py       HID transport (57-byte reports to 103c:84fd)  [verified]
  models.py       Color / Zone / Effect / Brightness
  protocol.py     model -> 57-byte frame builders               [PROVISIONAL]
  controller.py   high-level API + safety gate
  cli.py          command-line interface
  gui/            PySide6 app (app.py, widgets.py, profiles.py)
tools/
  CAPTURE_GUIDE.md   Windows USB capture procedure
  decode_pcap.py     pcapng -> diffed OUT frames
  PROTOCOL.md        byte-layout writeup (to fill)
udev/70-omen-tracerled.rules
```
