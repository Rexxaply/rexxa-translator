"""Kotak pesan bergaya Rexxa (dipakai untuk SEMUA alert aplikasi).

Tampilan Liquid Glass (lihat gui/glass.py): panel kaca frosted dengan animasi pop-up, lencana ikon bulat
berwarna sesuai jenis pesan, judul tebal di tengah, keterangan redup, lalu tombol kapsul selebar sama
(utama = gradasi biru-ungu, bahaya = merah lembut, biasa = kaca).

`MessageBox` adalah pengganti langsung QMessageBox untuk fungsi statis information / warning /
critical / question, jadi modul lain cukup mengimpor `MessageBox as QMessageBox`.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QSizePolicy

from .glass import MARGIN, GlassDialog

ACCENT = "#7c6cff"
KINDS = {   # warna lencana, simbol
    "info": ("#4f86ff", "i"),
    "success": ("#06d6a0", "✓"),
    "warn": ("#ffb020", "!"),
    "error": ("#ff6e7d", "×"),
    "question": ("#8e5cf6", "?"),
    "save": ("#ff9a62", "●"),
}

STYLE = """
QLabel#badge { border-radius: 22px; font-size: 17pt; font-weight: 800; color: white; }
QLabel#heading { font-family: 'Plus Jakarta Sans', 'Inter', 'Segoe UI', sans-serif; color: #f3f5fb; font-size: 12pt;
    font-weight: 800; }
QLabel#detail { color: rgba(228,232,245,0.66); font-size: 9.2pt; }
QPushButton { min-height: 36px; border-radius: 18px; padding: 0 18px; font-weight: 700; font-size: 9.5pt; }
QPushButton#primary { color: white; border: 1px solid rgba(255,255,255,0.22);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(111,143,232,0.95), stop:1 rgba(143,120,224,0.95)); }
QPushButton#primary:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7d9cf0, stop:1 #9d86ea); }
QPushButton#primary:pressed { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5f7fd8, stop:1 #7f68d2); }
QPushButton#danger { color: #ffb3ba; border: 1px solid rgba(255,120,135,0.40); background: rgba(255,110,125,0.14); }
QPushButton#danger:hover { background: rgba(255,110,125,0.26); color: #ffd0d5; }
QPushButton#neutral { color: #e6e9f4; border: 1px solid rgba(255,255,255,0.14);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,0.14), stop:1 rgba(255,255,255,0.05)); }
QPushButton#neutral:hover { background: rgba(255,255,255,0.18); }
QPushButton:focus { outline: none; }
"""


class Alert(GlassDialog):
    """Kotak pesan Liquid Glass. buttons: [(teks, gaya 'primary'|'danger'|'neutral', nilai_kembali)].
    exec_value() -> nilai tombol yang ditekan (Esc / tutup = escape_value)."""

    POP_IN_MS = 380

    def __init__(self, parent, title: str, heading: str, detail: str = "", kind: str = "info",
                 buttons=None, default_index: int = 0, escape_value=None):
        buttons = buttons or [("OK", "primary", True)]
        width = 400 if len(buttons) < 3 else 470
        super().__init__(parent, title or "Rexxa Translator", "", size=(width, 120), resizable=False, header=False)
        self.setObjectName("rexxaAlert")
        self.setStyleSheet(self.styleSheet() + STYLE)
        self.setModal(True)
        self._value = escape_value
        self._escape = escape_value
        self.sheet.layout().setContentsMargins(26, 22, 26, 20)

        color, glyph = KINDS.get(kind, KINDS["info"])
        badge = QLabel(glyph)
        badge.setObjectName("badge")
        badge.setFixedSize(44, 44)
        badge.setAlignment(Qt.AlignCenter)
        c = QColor(color)
        badge.setStyleSheet(
            "background: qradialgradient(cx:0.35, cy:0.3, radius:0.9, fx:0.35, fy:0.3, "
            f"stop:0 {c.lighter(135).name()}, stop:1 {c.name()}); border: 1px solid rgba(255,255,255,0.45);")
        brow = QHBoxLayout()
        brow.addStretch()
        brow.addWidget(badge)
        brow.addStretch()
        self.body.addLayout(brow)
        self.body.addSpacing(2)

        h = QLabel(heading)
        h.setObjectName("heading")
        h.setAlignment(Qt.AlignCenter)
        h.setWordWrap(True)
        h.setTextFormat(Qt.PlainText)
        self.body.addWidget(h)
        if detail:
            d = QLabel(detail)
            d.setObjectName("detail")
            d.setWordWrap(True)
            d.setTextFormat(Qt.PlainText)
            d.setTextInteractionFlags(Qt.TextSelectableByMouse)
            long_text = len(detail) > 160 or detail.count("\n") > 2
            d.setAlignment(Qt.AlignLeft if long_text else Qt.AlignCenter)
            self.body.addWidget(d)
        self.body.addSpacing(8)

        self._btns = []
        for i, (label, style, value) in enumerate(buttons):
            b = QPushButton(label)
            b.setObjectName(style)
            b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setMinimumWidth(104)
            b.clicked.connect(lambda _=False, val=value: self._done(val))
            self.footer.addWidget(b)
            self._btns.append(b)
        if self._btns:
            self._btns[min(default_index, len(self._btns) - 1)].setDefault(True)
            self._btns[min(default_index, len(self._btns) - 1)].setFocus()
        # tinggi mengikuti isi
        self.layout().activate()
        hint = self.sizeHint()
        self.resize(max(self.width(), min(hint.width(), 640 + 2 * MARGIN)), hint.height())

    def _done(self, val):
        self._value = val
        self.accept()

    def reject(self):          # Esc / tombol tutup jendela
        if self._closing is None:
            self._value = self._escape
        super().reject()

    def exec_value(self):
        self.exec()
        return self._value


def _split(text: str) -> tuple[str, str]:
    """Baris pertama = judul, sisanya = keterangan."""
    text = (text or "").strip()
    if "\n" in text:
        head, rest = text.split("\n", 1)
        return head.strip(), rest.strip()
    return text, ""


def show(parent, title, text, kind="info", ok="OK"):
    head, detail = _split(text)
    Alert(parent, title, head, detail, kind, [(ok, "primary", True)]).exec_value()


def ask(parent, title, text, yes="Ya", no="Tidak", kind="question", danger=False) -> bool:
    head, detail = _split(text)
    return bool(Alert(parent, title, head, detail, kind,
                      [(yes, "danger" if danger else "primary", True), (no, "neutral", False)],
                      escape_value=False).exec_value())


class MessageBox(QMessageBox):
    """Pengganti QMessageBox: fungsi statis memakai tampilan Rexxa. Enum (Yes, No, …) tetap sama."""

    @staticmethod
    def information(parent, title, text, *a, **k):
        show(parent, title, text, "info")
        return QMessageBox.Ok

    @staticmethod
    def warning(parent, title, text, *a, **k):
        show(parent, title, text, "warn")
        return QMessageBox.Ok

    @staticmethod
    def critical(parent, title, text, *a, **k):
        show(parent, title, text, "error")
        return QMessageBox.Ok

    @staticmethod
    def question(parent, title, text, *a, **k):
        return QMessageBox.Yes if ask(parent, title, text) else QMessageBox.No
