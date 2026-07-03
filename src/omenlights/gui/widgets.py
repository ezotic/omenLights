"""Reusable Qt widgets for the OmenLights GUI."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import Color, Zone


def _to_qcolor(c: Color) -> QColor:
    return QColor(c.r, c.g, c.b)


def _from_qcolor(q: QColor) -> Color:
    return Color(q.red(), q.green(), q.blue())


class ZoneSwatch(QWidget):
    """A labelled color swatch for one zone; click to pick a color."""

    colorChanged = Signal(int, object)  # (zone index, Color)

    def __init__(self, zone: Zone, color: Color, parent=None):
        super().__init__(parent)
        self.zone = zone
        self._color = color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self._swatch = QFrame()
        self._swatch.setFixedSize(120, 80)
        self._swatch.setFrameShape(QFrame.Box)
        self._swatch.setCursor(self.cursor())
        self._swatch.mousePressEvent = lambda _e: self._pick()  # type: ignore[assignment]

        self._label = QLabel(zone.name)
        self._hex = QLabel(f"#{color.to_hex()}")

        btn = QPushButton("Pick…")
        btn.clicked.connect(self._pick)

        layout.addWidget(self._label)
        layout.addWidget(self._swatch)
        layout.addWidget(self._hex)
        layout.addWidget(btn)
        self._refresh()

    @property
    def color(self) -> Color:
        return self._color

    def set_color(self, color: Color) -> None:
        self._color = color
        self._refresh()

    def _refresh(self) -> None:
        c = self._color
        self._swatch.setStyleSheet(f"background-color: rgb({c.r},{c.g},{c.b});")
        self._hex.setText(f"#{c.to_hex()}")

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(_to_qcolor(self._color), self, f"Pick color for {self.zone.name}")
        if chosen.isValid():
            self.set_color(_from_qcolor(chosen))
            self.colorChanged.emit(self.zone.index, self._color)


class ZoneGrid(QWidget):
    """A horizontal row of ZoneSwatch widgets."""

    colorChanged = Signal(int, object)

    def __init__(self, zones: list[Zone], parent=None):
        super().__init__(parent)
        self._row = QHBoxLayout(self)
        self.swatches: dict[int, ZoneSwatch] = {}
        for z in zones:
            sw = ZoneSwatch(z, Color(0, 0, 0))
            sw.colorChanged.connect(self.colorChanged)
            self.swatches[z.index] = sw
            self._row.addWidget(sw)

    def set_color(self, index: int, color: Color) -> None:
        self.swatches[index].set_color(color)

    def set_all(self, color: Color) -> None:
        for sw in self.swatches.values():
            sw.set_color(color)
