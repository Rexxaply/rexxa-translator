"""Pengaturan gradasi warna teks (seperti Gradient Tool di Photoshop)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDial, QDialog, QFormLayout, QGridLayout,
                               QHBoxLayout, QLabel, QPushButton, QSlider, QToolButton, QVBoxLayout, QWidget)

from core import gradient as G

# arah cepat: (teks tombol, sudut, keterangan)
DIRS = [("↘", 45, "Kiri-atas → kanan-bawah"), ("↓", 90, "Atas → bawah"), ("↙", 135, "Kanan-atas → kiri-bawah"),
        ("→", 0, "Kiri → kanan"), ("", None, ""), ("←", 180, "Kanan → kiri"),
        ("↗", 315, "Kiri-bawah → kanan-atas"), ("↑", 270, "Bawah → atas"), ("↖", 225, "Kanan-bawah → kiri-atas")]


def _lighter(hexc: str) -> str:
    c = QColor(hexc or "#000000")
    if c.lightness() < 60:
        return "#7A0A12"
    return c.lighter(150).name() if c.lightness() < 160 else c.darker(170).name()


class GradientDialog(QDialog):
    """Mengubah blok secara langsung; on_change() dipanggil setiap ada perubahan (render ulang)."""

    def __init__(self, block, on_change, parent=None):
        super().__init__(parent)
        self.b = block
        self.on_change = on_change
        self.setWindowTitle("Gradasi teks")
        self.setModal(False)
        self.resize(330, 0)
        if not self.b.color2:
            self.b.color2 = _lighter(self.b.color)
        v = QVBoxLayout(self)

        self.preview = QLabel("GRADASI")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedHeight(56)
        v.addWidget(self.preview)

        f = QFormLayout()
        f.setLabelAlignment(Qt.AlignRight)
        # warna
        crow = QHBoxLayout()
        self.c1 = QPushButton()
        self.c2 = QPushButton()
        for btn, attr, tip in ((self.c1, "color", "Warna awal"), (self.c2, "color2", "Warna akhir")):
            btn.setFixedSize(46, 24)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _=False, a=attr: self._pick(a))
        swap = QToolButton(text="⇄")
        swap.setToolTip("Tukar warna")
        swap.clicked.connect(self._swap)
        crow.addWidget(self.c1)
        crow.addWidget(swap)
        crow.addWidget(self.c2)
        crow.addStretch()
        f.addRow("Warna", crow)
        # jenis
        self.kind = QComboBox()
        for k, label in G.TYPES:
            self.kind.addItem(label, k)
        self.kind.currentIndexChanged.connect(self._changed)
        f.addRow("Bentuk", self.kind)
        # arah
        arow = QHBoxLayout()
        grid = QGridLayout()
        grid.setSpacing(2)
        self.dir_btns = []
        for i, (txt, ang, tip) in enumerate(DIRS):
            if ang is None:
                continue
            bt = QToolButton(text=txt)
            bt.setFixedSize(24, 24)
            bt.setToolTip(tip)
            bt.clicked.connect(lambda _=False, a=ang: self._set_angle(a))
            grid.addWidget(bt, i // 3, i % 3)
            self.dir_btns.append(bt)
        gw = QWidget()
        gw.setLayout(grid)
        arow.addWidget(gw)
        self.dial = QDial()
        self.dial.setRange(0, 359)
        self.dial.setWrapping(True)
        self.dial.setNotchesVisible(True)
        self.dial.setFixedSize(64, 64)
        self.dial.setToolTip("Putar untuk mengatur arah gradasi")
        self.dial.valueChanged.connect(self._dial)
        arow.addWidget(self.dial)
        self.ang_lbl = QLabel()
        self.ang_lbl.setMinimumWidth(36)
        arow.addWidget(self.ang_lbl)
        arow.addStretch()
        self.dir_row = QWidget()
        self.dir_row.setLayout(arow)
        f.addRow("Arah", self.dir_row)
        # posisi & kehalusan
        self.pos = QSlider(Qt.Horizontal)
        self.pos.setRange(0, 100)
        self.pos.setToolTip("Titik peralihan warna (seberapa jauh warna awal sebelum berganti)")
        self.pos.valueChanged.connect(self._changed)
        self.pos_lbl = QLabel()
        prow = QHBoxLayout()
        prow.addWidget(self.pos, 1)
        prow.addWidget(self.pos_lbl)
        f.addRow("Posisi", prow)
        self.soft = QSlider(Qt.Horizontal)
        self.soft.setRange(0, 100)
        self.soft.setToolTip("0 = batas tegas, 100 = peralihan halus penuh")
        self.soft.valueChanged.connect(self._changed)
        self.soft_lbl = QLabel()
        srow = QHBoxLayout()
        srow.addWidget(self.soft, 1)
        srow.addWidget(self.soft_lbl)
        f.addRow("Kehalusan", srow)
        self.per_line = QCheckBox("Ulangi gradasi di setiap baris")
        self.per_line.toggled.connect(self._changed)
        f.addRow("", self.per_line)
        v.addLayout(f)

        brow = QHBoxLayout()
        reset = QPushButton("Reset")
        reset.setToolTip("Linear, atas → bawah, halus")
        reset.clicked.connect(self._reset)
        off = QPushButton("Hapus gradasi")
        off.clicked.connect(self._off)
        close = QPushButton("Selesai")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        brow.addWidget(reset)
        brow.addWidget(off)
        brow.addStretch()
        brow.addWidget(close)
        v.addLayout(brow)
        self._load()

    # ------------------------------------------------------------------ data
    def _load(self):
        self._busy = True
        b = self.b
        i = self.kind.findData(b.grad_type or "linear")
        self.kind.setCurrentIndex(max(0, i))
        self.dial.setValue(int(round(((b.grad_angle if b.grad_angle is not None else 90) - 90) % 360)))
        self.pos.setValue(int(round((b.grad_pos if b.grad_pos is not None else 0.5) * 100)))
        self.soft.setValue(int(round((b.grad_soft if b.grad_soft is not None else 1.0) * 100)))
        self.per_line.setChecked(b.grad_scope == "line")
        self._busy = False
        self._refresh()

    def _refresh(self):
        b = self.b
        for btn, c in ((self.c1, b.color), (self.c2, b.color2)):
            btn.setStyleSheet(f"background:{c}; border:1px solid #4a4d57; border-radius:4px;")
        self.ang_lbl.setText(f"{int(round(b.grad_angle)) % 360}°")
        self.pos_lbl.setText(f"{self.pos.value()}%")
        self.soft_lbl.setText(f"{self.soft.value()}%")
        radial = (b.grad_type == "radial")
        self.dir_row.setEnabled(not radial)
        css = G.css_preview(b.grad_type, b.grad_angle, b.color, b.color2, b.grad_pos, b.grad_soft)
        self.preview.setStyleSheet(f"background:{css}; border-radius:6px; color:transparent;")

    def _changed(self, *_):
        if getattr(self, "_busy", False):
            return
        b = self.b
        b.grad_type = self.kind.currentData() or "linear"
        b.grad_pos = self.pos.value() / 100.0
        b.grad_soft = self.soft.value() / 100.0
        b.grad_scope = "line" if self.per_line.isChecked() else "block"
        if b.grad_type == "split" and self.soft.value() > 8:
            self._busy = True
            self.soft.setValue(0)
            self._busy = False
            b.grad_soft = 0.0
        self._refresh()
        self.on_change()

    def _dial(self, v):
        if getattr(self, "_busy", False):
            return
        # QDial: 0 di bawah; ubah ke sudut layar (90 = ke bawah)
        self.b.grad_angle = float((v + 90) % 360)
        self._changed()

    def _set_angle(self, a):
        self.b.grad_angle = float(a)
        self._busy = True
        self.dial.setValue(int((a - 90) % 360))
        self._busy = False
        self._changed()

    def _pick(self, attr):
        c = QColorDialog.getColor(QColor(getattr(self.b, attr) or "#000000"), self)
        if c.isValid():
            setattr(self.b, attr, c.name())
            self._changed()

    def _swap(self):
        self.b.color, self.b.color2 = self.b.color2, self.b.color
        self._changed()

    def _reset(self):
        b = self.b
        b.grad_type, b.grad_angle, b.grad_pos, b.grad_soft, b.grad_scope = "linear", 90.0, 0.5, 1.0, "block"
        self._load()
        self.on_change()

    def _off(self):
        self.b.color2 = ""
        self.on_change()
        self.accept()
