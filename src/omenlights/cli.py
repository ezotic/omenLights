"""Command-line interface for OmenLights.

Examples::

    omenlights info                 # show device presence / status
    omenlights list-zones
    omenlights zone 0 ff0000        # zone 0 -> red
    omenlights all 00ff00           # all zones -> green
    omenlights brightness 80
    omenlights effect wave --speed 5 --color 0000ff
    omenlights probe 00 01 00 ff 00 00   # send a raw frame (reverse-engineering)

Until the protocol is verified, commands that touch hardware require ``--force``.
"""

from __future__ import annotations

import sys
from typing import Optional

import typer

from . import protocol
from .controller import Controller, UnverifiedProtocolError
from .device import DeviceError, TracerLED
from .models import Brightness, Color, Effect

app = typer.Typer(add_completion=False, help=__doc__)

# Global flag set by the top-level callback.
_state = {"force": False}


@app.callback()
def _root(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Send frames even though the protocol is not yet verified.",
    ),
) -> None:
    _state["force"] = force


def _controller() -> Controller:
    return Controller(allow_unverified=_state["force"])


def _run(fn) -> None:
    try:
        with _controller() as ctrl:
            fn(ctrl)
    except UnverifiedProtocolError as exc:
        typer.secho(str(exc), fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(2)
    except DeviceError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command()
def info() -> None:
    """Report whether the TracerLED controller is present and protocol status."""
    present = TracerLED.is_present()
    typer.echo(f"TracerLED present: {present}")
    typer.echo(f"Protocol verified: {protocol.VERIFIED}")
    if not protocol.VERIFIED:
        typer.secho(
            "Protocol is still PROVISIONAL -- decode a capture before trusting "
            "hardware output (see tools/CAPTURE_GUIDE.md).",
            fg=typer.colors.YELLOW,
        )


@app.command("list-zones")
def list_zones() -> None:
    """List controllable lighting zones."""
    from .models import ZONES

    for z in ZONES:
        typer.echo(f"{z.index}: {z.name}")


@app.command()
def zone(index: int, color: str) -> None:
    """Set ZONE INDEX to COLOR (hex RRGGBB)."""
    c = Color.from_hex(color)
    _run(lambda ctrl: ctrl.set_zone(index, c))


@app.command()
def all(color: str) -> None:
    """Set all zones to COLOR (hex RRGGBB)."""
    c = Color.from_hex(color)
    _run(lambda ctrl: ctrl.set_all(c))


@app.command()
def brightness(percent: int) -> None:
    """Set master brightness (0..100)."""
    b = Brightness(percent)
    _run(lambda ctrl: ctrl.set_brightness(b))


@app.command()
def off() -> None:
    """Turn all zones off (black)."""
    _run(lambda ctrl: ctrl.off())


@app.command()
def effect(
    name: str,
    color: Optional[str] = typer.Option(None, "--color", help="Hex RRGGBB"),
    speed: int = typer.Option(5, "--speed", min=1, max=10, help="Effect speed 1-10"),
) -> None:
    """Run an effect: static, breathing, color_cycle, wave, blink.

    Animated effects run until you press Ctrl+C.
    """
    try:
        eff = Effect(name)
    except ValueError:
        valid = ", ".join(e.value for e in Effect)
        typer.secho(f"unknown effect {name!r}; choose from: {valid}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    c = Color.from_hex(color) if color else None
    if eff is not Effect.STATIC:
        typer.echo(f"Running {eff.value} (Ctrl+C to stop)…")
    _run(lambda ctrl: ctrl.run_effect(eff, color=c, speed=speed))


@app.command()
def probe(bytes_hex: list[str]) -> None:
    """Send a raw frame given as space-separated hex bytes (reverse-engineering).

    Example: omenlights --force probe 00 01 00 ff 00 00
    """
    try:
        payload = bytes(int(b, 16) for b in bytes_hex)
    except ValueError:
        typer.secho("arguments must be hex bytes, e.g. 00 01 ff", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    _run(lambda ctrl: ctrl.send_raw(payload))
    typer.echo(f"sent {len(payload)} bytes: {payload.hex(' ')}")


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
