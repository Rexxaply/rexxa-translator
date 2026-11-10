"""Kotak pesan bergaya Rexxa (dipakai untuk SEMUA alert aplikasi).

Tampilan: kartu gelap, lencana ikon bulat berwarna sesuai jenis pesan, judul tebal di tengah,
keterangan redup di bawahnya, lalu tombol-tombol selebar sama (utama = merah muda penuh,
bahaya = merah lembut, biasa = abu-abu gelap).

`MessageBox` adalah pengganti langsung QMessageBox untuk fungsi statis information / warning /
critical / question, jadi modul lain cukup mengimpor `MessageBox as QMessageBox`.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout,
                               QWidget)

ACCENT = "#ff4d6d"
KINDS = {   # warna lencana, simbol
    "info": ("#3a86ff", "i"),
    "success": ("#06d6a0", "✓"),
    "warn": ("#ffb020", "!"),
    "error": ("#ff4d6d", "×"),
    "question": ("#c77dff", "?"),
    "save": ("#ff4d6d", "●"),
}

STYLE = f"""
QDialog#rexxaAlert {{ background: #17181d; }}
QWidget#card {{ background: #1d1e24; border: 1px solid #2b2d35; border-radius: 12px; }}
QLabel#badge {{ border-radius: 20px; font-size: 17pt; font-weight: 800; color: #111; }}
QLabel#heading {{ color: #f1f2f5; font-size: 11pt; font-weight: 700; background: transparent; }}
QLabel#detail {{ color: #8f93a0; font-size: 9pt; background: transparent; }}
QPushButton {{ min-height: 34px; border-radius: 8px; padding: 0 18px; font-weight: 600; font-size: 9.5pt; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: none; }}
QPushButton#primary:hover {{ background: #ff6b85; }}
QPushButton#primary:pressed {{ background: #e63d5c; }}
QPushButton#danger {{ background: rgba(255, 77, 109, 0.12); color: #ff8a9b; border: 1px solid rgba(255, 77, 109, 0.45); }}
QPushButton#danger:hover {{ background: rgba(255, 77, 109, 0.22); color: #ffb3bf; }}
QPushButton#neutral {{ background: #2a2c34; color: #d6d8de; border: 1px solid #353841; }}
QPushButton#neutral:hover {{ background: #33363f; }}
QPushButton:focus {{ outline: none; }}
"""


class Alert(QDialog):
    """buttons: [(teks, gaya 'primary'|'danger'|'neutral', nilai_kembali)]. exec_value() -> nilai."""

    def __init__(self, parent, title: str, heading: str, detail: str = "", kind: str = "info",
                 buttons=None, default_index: int = 0, escape_value=None):
        super().__init__(parent)
        self.setObjectName("rexxaAlert")
        self.setWindowTitle(title or "Rexxa Translator")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setStyleSheet(STYLE)
        self.setModal(True)
        self._value = escape_value
        self._escape = escape_value
        buttons = buttons or [("OK", "primary", True)]

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        card = QWidget()
        card.setObjectName("card")
        v = QVBoxLayout(card)
        v.setContentsMargins(24, 22, 24, 20)
        v.setSpacing(8)

        color, glyph = KINDS.get(kind, KINDS["info"])
        badge = QLabel(glyph)
        badge.setObjectName("badge")
        badge.setFixedSize(40, 40)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"background: {color};")
        brow = QHBoxLayout()
        brow.addStretch()
        brow.addWidget(badge)
        brow.addStretch()
        v.addLayout(brow)
        v.addSpacing(4)

        h = QLabel(heading)
        h.setObjectName("heading")
        h.setAlignment(Qt.AlignCenter)
        h.setWordWrap(True)
        h.setTextFormat(Qt.PlainText)
        v.addWidget(h)
        if detail:
            d = QLabel(detail)
            d.setObjectName("detail")
            d.setWordWrap(True)
            d.setTextFormat(Qt.PlainText)
            d.setTextInteractionFlags(Qt.TextSelectableByMouse)
            long_text = len(detail) > 160 or detail.count("\n") > 2
            d.setAlignment(Qt.AlignLeft if long_text else Qt.AlignCenter)
            v.addWidget(d)
        v.addSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(10)
        self._btns = []
        for i, (label, style, value) in enumerate(buttons):
            b = QPushButton(label)
            b.setObjectName(style)
            b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setMinimumWidth(104)
            b.clicked.connect(lambda _=False, val=value: self._done(val))
            row.addWidget(b)
            self._btns.append(b)
        v.addLayout(row)
        outer.addWidget(card)
        if self._btns:
            self._btns[min(default_index, len(self._btns) - 1)].setDefault(True)
            self._btns[min(default_index, len(self._btns) - 1)].setFocus()
        self.setMinimumWidth(400 if len(buttons) < 3 else 460)
        self.setMaximumWidth(620)

    def _done(self, val):
        self._value = val
        self.accept()

    def reject(self):          # Esc / tombol tutup jendela
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
