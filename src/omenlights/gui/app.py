"""OmenLights GUI main window -- a Light Studio-style front end.

Safety: because the wire protocol is still PROVISIONAL (protocol.VERIFIED is
False), "Send to hardware" is OFF by default. The UI works as a live preview;
tick the checkbox only once you intend to probe the real controller.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .. import protocol
from ..controller import Controller, UnverifiedProtocolError
from ..device import DeviceError, TracerLED
from ..models import ZONES, Brightness, Color, Effect
from .profiles import Profile, list_profiles
from .widgets import ZoneGrid


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OmenLights")
        self._build()
        self._refresh_status()

    # -- UI construction ---------------------------------------------------
    def _build(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        self.status_label = QLabel()
        root.addWidget(self.status_label)

        # Zones
        root.addWidget(QLabel("Zones"))
        self.grid = ZoneGrid(list(ZONES))
        self.grid.colorChanged.connect(self._on_zone_color)
        root.addWidget(self.grid)

        # All-zones quick set
        all_row = QHBoxLayout()
        all_btn = QPushButton("Set all zones…")
        all_btn.clicked.connect(self._set_all)
        all_row.addWidget(all_btn)
        all_row.addStretch()
        root.addLayout(all_row)

        # Brightness
        b_row = QHBoxLayout()
        b_row.addWidget(QLabel("Brightness"))
        self.brightness = QSlider(Qt.Horizontal)
        self.brightness.setRange(0, 100)
        self.brightness.setValue(100)
        self.brightness.sliderReleased.connect(self._on_brightness)
        self.brightness_val = QLabel("100%")
        self.brightness.valueChanged.connect(lambda v: self.brightness_val.setText(f"{v}%"))
        b_row.addWidget(self.brightness)
        b_row.addWidget(self.brightness_val)
        root.addLayout(b_row)

        # Effect
        e_row = QHBoxLayout()
        e_row.addWidget(QLabel("Effect"))
        self.effect = QComboBox()
        for eff in Effect:
            self.effect.addItem(eff.value, eff)
        e_row.addWidget(self.effect)
        e_row.addWidget(QLabel("Speed"))
        self.speed = QSlider(Qt.Horizontal)
        self.speed.setRange(1, 10)
        self.speed.setValue(5)
        e_row.addWidget(self.speed)
        apply_eff = QPushButton("Apply effect")
        apply_eff.clicked.connect(self._on_effect)
        e_row.addWidget(apply_eff)
        root.addLayout(e_row)

        # Profiles
        p_row = QHBoxLayout()
        save_btn = QPushButton("Save profile…")
        save_btn.clicked.connect(self._save_profile)
        load_btn = QPushButton("Load profile…")
        load_btn.clicked.connect(self._load_profile)
        p_row.addWidget(save_btn)
        p_row.addWidget(load_btn)
        p_row.addStretch()
        root.addLayout(p_row)

        # Hardware safety toggle
        self.send_hw = QCheckBox("Send to hardware (protocol unverified — use with care)")
        self.send_hw.setChecked(False)
        root.addWidget(self.send_hw)

        self.setCentralWidget(central)

    # -- status ------------------------------------------------------------
    def _refresh_status(self) -> None:
        present = TracerLED.is_present()
        verified = protocol.VERIFIED
        msg = f"Device: {'connected' if present else 'not found'}   |   "
        msg += f"Protocol: {'verified' if verified else 'PROVISIONAL'}"
        self.status_label.setText(msg)
        if not present:
            self.send_hw.setChecked(False)
            self.send_hw.setEnabled(False)

    # -- controller helper -------------------------------------------------
    def _apply(self, fn) -> None:
        """Run fn(controller) if 'send to hardware' is enabled; else preview-only."""
        if not self.send_hw.isChecked():
            return  # preview only -- swatches already reflect state
        try:
            with Controller(allow_unverified=True) as ctrl:
                fn(ctrl)
        except UnverifiedProtocolError as exc:
            QMessageBox.warning(self, "Unverified protocol", str(exc))
        except DeviceError as exc:
            QMessageBox.critical(self, "Device error", str(exc))

    # -- handlers ----------------------------------------------------------
    def _on_zone_color(self, index: int, color: Color) -> None:
        self._apply(lambda c: c.set_zone(index, color))

    def _set_all(self) -> None:
        from PySide6.QtWidgets import QColorDialog

        chosen = QColorDialog.getColor(QColor(255, 255, 255), self, "Set all zones")
        if not chosen.isValid():
            return
        color = Color(chosen.red(), chosen.green(), chosen.blue())
        self.grid.set_all(color)
        self._apply(lambda c: c.set_all(color))

    def _on_brightness(self) -> None:
        v = self.brightness.value()
        self._apply(lambda c: c.set_brightness(Brightness(v)))

    def _on_effect(self) -> None:
        eff: Effect = self.effect.currentData()
        speed = self.speed.value()
        # Stop any running effect first.
        self._stop_effect()
        if eff is Effect.STATIC:
            # Re-apply the current per-zone swatch colors.
            self._apply(
                lambda c: [c.set_zone(i, sw.color) for i, sw in self.grid.swatches.items()]
            )
            return
        if not self.send_hw.isChecked():
            QMessageBox.information(self, "Preview only", "Tick 'Send to hardware' to run effects on the device.")
            return
        import threading

        self._effect_stop = threading.Event()

        def run():
            try:
                with Controller(allow_unverified=True) as ctrl:
                    ctrl.run_effect(eff, speed=speed, stop=self._effect_stop)
            except (UnverifiedProtocolError, DeviceError):
                pass

        self._effect_thread = threading.Thread(target=run, daemon=True)
        self._effect_thread.start()

    def _stop_effect(self) -> None:
        ev = getattr(self, "_effect_stop", None)
        if ev is not None:
            ev.set()
        th = getattr(self, "_effect_thread", None)
        if th is not None:
            th.join(timeout=1.0)
        self._effect_stop = None
        self._effect_thread = None

    # -- profiles ----------------------------------------------------------
    def _current_profile(self, name: str) -> Profile:
        return Profile(
            name=name,
            zone_colors={i: sw.color.to_hex() for i, sw in self.grid.swatches.items()},
            brightness=self.brightness.value(),
            effect=self.effect.currentData().value,
        )

    def _save_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:")
        if ok and name:
            path = self._current_profile(name).save()
            QMessageBox.information(self, "Saved", f"Saved to {path}")

    def _load_profile(self) -> None:
        names = list_profiles()
        if not names:
            QMessageBox.information(self, "No profiles", "No saved profiles yet.")
            return
        name, ok = QInputDialog.getItem(self, "Load profile", "Profile:", names, 0, False)
        if not (ok and name):
            return
        prof = Profile.load(name)
        for i, sw in self.grid.swatches.items():
            sw.set_color(prof.color_for(i))
        self.brightness.setValue(prof.brightness)
        idx = self.effect.findData(Effect(prof.effect))
        if idx >= 0:
            self.effect.setCurrentIndex(idx)
        # Push the loaded state to hardware if enabled.
        self._apply(lambda c: [c.set_zone(i, sw.color) for i, sw in self.grid.swatches.items()])


def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(720, 480)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
