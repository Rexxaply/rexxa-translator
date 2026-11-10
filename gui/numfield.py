"""Kolom angka ringkas untuk panel Tipografi.

Dibuat dari QLineEdit (bukan QSpinBox): QSpinBox tanpa tombol di dalam kotak bergaya
kadang tidak menggambar teksnya di Windows, jadi nilainya tidak terlihat.
Mendukung: ketik angka (Enter / pindah fokus), panah atas/bawah, roda mouse, teks khusus
untuk nilai minimum (mis. "Auto"), dan akhiran (mis. "°")."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLineEdit


class NumField(QLineEdit):
    valueChanged = Signal(float)

    def __init__(self, lo, hi, step=1, decimals=0, special="", suffix="", parent=None, default=None):
        super().__init__(parent)
        self._lo, self._hi, self._step, self._dec = float(lo), float(hi), float(step), int(decimals)
        self._special, self._suffix = special or "", suffix or ""
        self._val = float(min(hi, max(lo, 0.0 if default is None else default))) if not special else float(lo)
        self.setAlignment(Qt.AlignCenter)
        self.setObjectName("numField")
        self.setMinimumWidth(26)
        self.setFixedHeight(22)
        self.editingFinished.connect(self._commit_text)
        self._show()

    # ---- API mirip QSpinBox
    def value(self):
        return round(self._val, self._dec) if self._dec else int(round(self._val))

    def setValue(self, v, emit=False):
        v = min(self._hi, max(self._lo, float(v)))
        changed = abs(v - self._val) > 1e-9
        self._val = v
        self._show()
        if changed and emit:
            self.valueChanged.emit(self.value())

    def setSpecialValueText(self, text):
        self._special = text or ""
        self._show()

    def setRange(self, lo, hi):
        self._lo, self._hi = float(lo), float(hi)
        self.setValue(self._val)

    # ---- tampilan
    def _fmt(self, v):
        return (f"{v:.{self._dec}f}" if self._dec else str(int(round(v)))) + self._suffix

    def _show(self):
        if self._special and abs(self._val - self._lo) < 1e-9:
            self.setText(self._special)
        else:
            self.setText(self._fmt(self._val))
        self.setCursorPosition(0)

    def _commit_text(self):
        t = self.text().strip().replace(",", ".")
        if self._suffix:
            t = t.replace(self._suffix, "")
        if self._special and (t == self._special or t.lower().startswith(self._special.split()[0].lower())):
            self.setValue(self._lo, emit=True)
            return
        try:
            self.setValue(float(t), emit=True)
        except ValueError:
            self._show()

    def _bump(self, n):
        self.setValue(self._val + n * self._step, emit=True)

    def keyPressEvent(self, e):
        k = e.key()
        mult = 10 if e.modifiers() & Qt.ShiftModifier else 1
        if k == Qt.Key_Up:
            self._bump(mult)
        elif k == Qt.Key_Down:
            self._bump(-mult)
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            self._commit_text()
            self.selectAll()
        else:
            super().keyPressEvent(e)

    def wheelEvent(self, e):
        if not self.hasFocus() and not self.underMouse():
            return super().wheelEvent(e)
        d = e.angleDelta().y()
        if d:
            self._bump(1 if d > 0 else -1)
            e.accept()

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.selectAll()
