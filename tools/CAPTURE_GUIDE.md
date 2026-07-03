# Capturing the OMEN Light Studio USB protocol (Windows)

Goal: record the exact 57-byte HID frames that OMEN Light Studio sends to the
`HP TracerLED` controller (`103c:84fd`) while we change colors/effects, so we can
decode the byte layout on Linux. The capture must be **scripted and
single-variable** — change one thing at a time, with pauses — or the byte diff
is ambiguous.

You only have to do this once.

## 1. Install the capture tools (Windows)

1. Install **Wireshark** (https://www.wireshark.org/download.html). During
   setup, **enable the USBPcap component** (checkbox in the installer). USBPcap
   is what lets Wireshark see USB traffic.
2. Reboot if the installer asks (USBPcap installs a driver).

## 2. Identify the TracerLED's USBPcap interface

1. Open **Wireshark**. In the interface list you'll see `USBPcap1`, `USBPcap2`,
   etc. (one per USB root hub).
2. Easiest path: just capture on **all USBPcap interfaces** and we filter later.
   Double-click `USBPcap1` (or select several and start).
3. (Optional) To find which hub the device is on, open Device Manager → View →
   Devices by connection, and locate "HP TracerLED" / an HID device under a hub.

## 3. Record the scripted sequence

Start the Wireshark capture, then open **OMEN Light Studio** and perform the
following **slowly**, pausing ~3 seconds between each step so the frames are easy
to separate in time. Keep a written log of what you did and roughly when
(step number is enough).

> If Light Studio uses "zones", do these per zone where noted. If it only offers
> whole-system color, just do the global versions.

**A. Baseline**
1. Set the whole system to **OFF / black** (or lowest brightness). Pause.

**B. Single zone, primary colors** (pick ONE zone, e.g. the front logo)
2. Zone → pure **RED**   `#FF0000`. Pause.
3. Zone → pure **GREEN** `#00FF00`. Pause.
4. Zone → pure **BLUE**  `#0000FF`. Pause.
5. Zone → **WHITE**      `#FFFFFF`. Pause.
6. Zone → a distinctive value, e.g. `#102030`. Pause.

**C. Second zone** (if more than one zone exists)
7. A *different* zone → pure **RED**. Pause.  (lets us find the zone-index byte)

**D. All zones**
8. All zones → **RED** at once (if there's an "apply to all"). Pause.

**E. Brightness** (set a solid color first, e.g. white, then)
9. Brightness **0%**. Pause.
10. Brightness **50%**. Pause.
11. Brightness **100%**. Pause.

**F. Effects** — activate each available effect one at a time, pausing between:
12. Static, 13. Breathing, 14. Color cycle, 15. Wave, 16. Blink, … (whatever the
    app offers). For effects with a color, use RED so the color bytes are obvious.

Stop the capture.

## 4. Save and transfer to Linux

1. **File → Save As** → `omen-capture.pcapng` (keep the pcapng format).
2. Copy it somewhere Linux can read — e.g. the shared `GAMES` (sdb3) or
   `Windows` partition, or a USB stick, or the NAS. Then on Linux drop it into
   this repo, e.g. `tools/captures/omen-capture.pcapng`.

## 5. Hand it back

Tell me the path to the `.pcapng` and your step log (which step was which color/
effect). I'll run `tools/decode_pcap.py` to extract and diff the OUT frames, work
out the byte layout, write `tools/PROTOCOL.md`, and fill in `protocol.py`.

---

### Notes / troubleshooting
- We only care about **OUT** transfers (host → device) to `103c:84fd`. The
  decoder filters these automatically.
- If USBPcap shows nothing for the device, the controller may be on a different
  root hub — capture on all `USBPcapN` interfaces simultaneously.
- The frames are 57 bytes of payload (USBPcap may show 64-byte URBs; trailing
  bytes are padding). The decoder handles both.
