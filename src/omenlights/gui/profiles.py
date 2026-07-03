"""Saving/loading lighting profiles to ~/.config/omenlights/."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..models import Color, Effect


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    d = Path(base) / "omenlights"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Profile:
    """A snapshot of lighting state the GUI can save and re-apply."""

    name: str = "Untitled"
    zone_colors: dict[int, str] = field(default_factory=dict)  # zone index -> hex
    brightness: int = 100
    effect: str = Effect.STATIC.value

    def color_for(self, index: int) -> Color:
        hexstr = self.zone_colors.get(index, "000000")
        return Color.from_hex(hexstr)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "Profile":
        d = json.loads(text)
        # JSON object keys are strings; normalize zone indices back to int.
        d["zone_colors"] = {int(k): v for k, v in d.get("zone_colors", {}).items()}
        return cls(**d)

    def save(self) -> Path:
        path = config_dir() / f"{self.name}.json"
        path.write_text(self.to_json())
        return path

    @classmethod
    def load(cls, name: str) -> "Profile":
        return cls.from_json((config_dir() / f"{name}.json").read_text())


def list_profiles() -> list[str]:
    return sorted(p.stem for p in config_dir().glob("*.json"))
