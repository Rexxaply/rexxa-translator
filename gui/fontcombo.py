"""Pilihan font yang menampilkan nama tiap font DENGAN font itu sendiri (pratinjau langsung),
jadi font yang cocok bisa dipilih tanpa mencoba satu per satu.

Font baru didaftarkan ke Qt saat daftar pertama kali dibuka (bukan saat aplikasi mulai),
dan hasilnya disimpan supaya membuka daftar berikutnya instan."""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics
from PySide6.QtWidgets import QComboBox, QStyle, QStyledItemDelegate

PREVIEW_PT = 11.5
_cache: dict = {}            # path -> QFont | None


def qfont_for(path: str, pt: float = PREVIEW_PT):
    """QFont untuk file font (gaya persis: Bold, Italic, dst.), atau None bila tidak bisa dimuat."""
    if not path:
        return None
    key = (path, pt)
    if key in _cache:
        return _cache[key]
    f = None
    try:
        fid = QFontDatabase.addApplicationFont(path)
        fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        if fams:
            fam = fams[0]
            style = ""
            try:
                from PIL import ImageFont
                style = ImageFont.truetype(path, 12).font.style or ""
            except Exception:
                pass
            f = QFontDatabase.font(fam, style, int(round(pt))) if style else QFont(fam)
            if f.family() != fam:
                f = QFont(fam)
            f.setPointSizeF(pt)
            low = style.lower()
            if "bold" in low or "black" in low or "heavy" in low:
                f.setBold(True)
            if "italic" in low or "oblique" in low:
                f.setItalic(True)
    except Exception:
        f = None
    _cache[key] = f
    return f


class _Delegate(QStyledItemDelegate):
    """Menggambar teks tiap baris dengan font miliknya (stylesheet aplikasi tidak menimpanya)."""

    def paint(self, painter, option, index):
        self.initStyleOption(option, index)
        f = index.data(Qt.FontRole)
        text = option.text
        option.text = ""
        style = option.widget.style() if option.widget else None
        if style:
            style.drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)
        painter.save()
        if isinstance(f, QFont):
            painter.setFont(f)
        sel = bool(option.state & QStyle.State_Selected)
        painter.setPen(Qt.white if sel else option.palette.text().color())
        r = QRect(option.rect.adjusted(10, 0, -6, 0))
        fm = QFontMetrics(painter.font())
        painter.drawText(r, Qt.AlignVCenter | Qt.AlignLeft, fm.elidedText(text, Qt.ElideRight, r.width()))
        painter.restore()

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        f = index.data(Qt.FontRole)
        h = QFontMetrics(f).height() + 10 if isinstance(f, QFont) else s.height() + 6
        return QSize(s.width(), max(28, min(46, h)))


class FontCombo(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_Delegate(self))
        self.setMaxVisibleItems(16)

    def showPopup(self):
        for i in range(self.count()):
            if self.itemData(i, Qt.FontRole) is None:
                f = qfont_for(self.itemData(i) or "")
                if f is not None:
                    self.setItemData(i, f, Qt.FontRole)
        w = max(self.width(), 260)
        self.view().setMinimumWidth(w)
        super().showPopup()
