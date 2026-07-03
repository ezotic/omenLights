# TracerLED (103c:84fd) wire protocol — DECODED

Status: **VERIFIED** from a USBPcap capture of OMEN Light Studio on an OMEN 30L
(`omen.pcapng`, 87 OUT frames, device address 3). `protocol.VERIFIED = True`.

## Transport (from on-device discovery)

| Property     | Value                                                |
|--------------|------------------------------------------------------|
| USB id       | `103c:84fd` ("HP TracerLED")                          |
| Interface    | HID, hid-generic, `/dev/hidraw0`                      |
| OUT endpoint | `0x02`, interrupt, 64-byte max packet                |
| Report       | unnumbered, **57 bytes** payload                     |
| hidapi write | 58 bytes (`0x00` report id + 57 payload)             |

## Frame layout (57 bytes)

Every OUT frame observed has **exactly one form** — a per-zone "set color":

```
off  0  1  2  3   4  5  6   7  8  9  10 11 12  13 14 15 ......  47 48  49 50 51 52  53 54  55 56
    3b 12 01 01  [z0 unused] [ zone1 ] [ zone2 ] [ zone3 ] 0..  64 0a  00 00 00 00  ZZ 01  00 00
    \__header__/  \___ RGB triples, one per zone, at offset 4+3*zone ___/  \const/          \zone/
```

- **bytes 0–3** — constant header `3b 12 01 01`.
- **RGB triple for zone `z`** lives at offset **`4 + 3*z`** (z is 1-based):
  zone 1 → bytes 7–9, zone 2 → 10–12, zone 3 → 13–15. Channel order is **R, G, B**.
  (There is an unused slot 0 at bytes 4–6; the app never writes it.)
- **byte 47 = `0x64` (100)** — constant. Likely a global brightness field left at
  max; the app does brightness by scaling RGB host-side instead (see below).
- **byte 48 = `0x0a` (10)** — constant (unknown; possibly a default speed/param).
- **byte 53 = zone id** (`0x01`, `0x02`, `0x03`) — which zone this frame updates.
- **byte 54 = `0x01`** — constant.
- All other bytes `0x00`.

Each frame carries **one** zone's color (both byte 53 and the RGB offset encode
the same zone — redundant but that's what the app sends). Setting all zones =
send 3 frames, zone id 1, 2, 3.

### Verified frames (byte-exact)

Pure red on each zone (capture idx 7685/7688/7691, t≈47.1s):
```
zone1: 3b 12 01 01 00 00 00 ff 00 00 00 00 00 00 00 00 ...0... 64 0a 00 00 00 00 01 01 00 00
zone2: 3b 12 01 01 00 00 00 00 00 00 ff 00 00 00 00 00 ...0... 64 0a 00 00 00 00 02 01 00 00
zone3: 3b 12 01 01 00 00 00 00 00 00 00 00 00 ff 00 00 ...0... 64 0a 00 00 00 00 03 01 00 00
```
Pure white zone1 (idx 9574): `...4+3 = ff ff ff...`, byte53=`01`.

## Brightness & effects = host-driven

The capture shows **no** distinct brightness or effect opcode — the header is
identical in all 87 frames. What look like effects are the app **streaming
color frames over time**:

- A fade/breathe appears as a ramp of scaled RGB, e.g.
  `15 ff 0a → 12 e5 08 → 0f bc 07 → … → 01 0f 00` (same hue, decreasing
  magnitude). ⇒ **brightness = multiply each channel by percent/100 on the host.**
- Color transitions / cycles are just successive `set zone` frames.

So OmenLights implements brightness by scaling RGB and implements animated
effects (breathing, color-cycle, blink, wave) by streaming `set zone` frames
from the host — mirroring Light Studio.

## Zones

This machine exposes **3 zones** (ids 1, 2, 3). More zones, if present, would use
the next offsets (`4+3*z`) / byte-53 ids; probe with `omenlights --force probe …`
to discover any beyond 3.

## Open / not needed

- byte 47 (`0x64`) and byte 48 (`0x0a`): constant; may be firmware brightness /
  speed. Left at observed values. Could be probed later, not required for control.
