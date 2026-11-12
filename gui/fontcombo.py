"""Pilihan font yang menampilkan nama tiap font DENGAN font itu sendiri (pratinjau langsung),
jadi font yang cocok bisa dipilih tanpa mencoba satu per satu.

Kotaknya juga bisa diketik: daftar langsung tersaring ke font yang namanya mengandung ketikan
(di bagian mana saja, huruf besar/kecil tidak berpengaruh), bagian yang cocok disorot.

Font baru didaftarkan ke Qt saat daftar pertama kali dibuka (bukan saat aplikasi mulai),
dan hasilnya disimpan supaya membuka daftar berikutnya instan."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, QSize, QSortFilterProxyModel, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics
from PySide6.QtWidgets import QComboBox, QCompleter, QListView, QStyle, QStyledItemDelegate

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
    """Menggambar teks tiap baris dengan font miliknya (stylesheet aplikasi tidak menimpanya).
    `query`: teks pencarian -> bagian nama yang cocok diberi sorotan."""

    def __init__(self, parent=None, query=None):
        super().__init__(parent)
        self.query = query or (lambda: "")

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
        shown = fm.elidedText(text, Qt.ElideRight, r.width())
        q = (self.query() or "").strip()
        k = shown.lower().find(q.lower()) if q else -1
        if k >= 0:                       # sorot bagian yang cocok dengan ketikan
            x = r.left() + fm.horizontalAdvance(shown[:k])
            wq = fm.horizontalAdvance(shown[k:k + len(q)])
            hl = QRect(x - 1, r.center().y() - fm.height() // 2, wq + 2, fm.height())
            painter.setRenderHint(painter.RenderHint.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(160, 150, 235, 95))
            painter.drawRoundedRect(hl, 3, 3)
            painter.setPen(Qt.white if sel else option.palette.text().color())
        painter.drawText(r, Qt.AlignVCenter | Qt.AlignLeft, shown)
        painter.restore()

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        f = index.data(Qt.FontRole)
        h = QFontMetrics(f).height() + 10 if isinstance(f, QFont) else s.height() + 6
        return QSize(s.width(), max(28, min(46, h)))


class _Filter(QSortFilterProxyModel):
    """Nama font yang MENGANDUNG ketikan (bukan hanya diawali), urut: yang diawali ketikan dulu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.q = ""
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    def set_query(self, q: str):
        self.q = (q or "").strip().lower()
        self.invalidate()
        self.sort(0 if self.q else -1)

    def filterAcceptsRow(self, row, parent):
        if not self.q:
            return True
        t = (self.sourceModel().index(row, 0, parent).data() or "").lower()
        return all(w in t for w in self.q.split())

    def lessThan(self, a, b):
        ta, tb = (a.data() or "").lower(), (b.data() or "").lower()
        ka, kb = (not ta.startswith(self.q), a.row()), (not tb.startswith(self.q), b.row())
        return ka < kb


class FontCombo(QComboBox):
    """Dropdown font yang bisa diketik untuk mencari (tersaring seketika di setiap ketikan)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_Delegate(self))
        self.setMaxVisibleItems(14)          # sisanya digulir (scroll)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        le = self.lineEdit()
        le.setPlaceholderText("Ketik untuk cari font…")
        try:
            from .icons import icon
            from PySide6.QtWidgets import QLineEdit
            le.addAction(icon("search", "#9aa3bb"), QLineEdit.LeadingPosition)
        except Exception:
            pass
        # pencarian: daftar tersaring seketika, fokus tetap di kotak ketik
        self._proxy = _Filter(self)
        self._proxy.setSourceModel(self.model())
        self._comp = QCompleter(self)
        self._comp.setModel(self._proxy)
        self._comp.setCompletionMode(QCompleter.UnfilteredPopupCompletion)   # penyaringan diurus _Filter
        self._comp.setCaseSensitivity(Qt.CaseInsensitive)
        self._comp.setMaxVisibleItems(12)
        pop = QListView()
        pop.setObjectName("fontSearch")
        pop.setUniformItemSizes(False)
        pop.setItemDelegate(_Delegate(pop, query=lambda: self._proxy.q))
        pop.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._comp.setPopup(pop)
        try:                                  # panel kaca membulat seperti dropdown lain
            from .glass import _PopupFx
            _PopupFx._prep(pop)
        except Exception:
            pass
        self.setCompleter(None)
        self._comp.setWidget(le)
        pop.clicked.connect(lambda ix: self._picked(ix.data()))
        self._fresh = False
        le.textEdited.connect(self._typed)
        le.returnPressed.connect(self._enter)
        le.installEventFilter(self)
        pop.installEventFilter(self)

    # ---------------------------------------------------------------- pencarian
    def _ensure_fonts(self):
        for i in range(self.count()):
            if self.itemData(i, Qt.FontRole) is None:
                f = qfont_for(self.itemData(i) or "")
                if f is not None:
                    self.setItemData(i, f, Qt.FontRole)

    def _typed(self, text):
        le = self.lineEdit()
        if self._fresh:
            # ketikan pertama setelah kotak diklik: nama font lama tidak ikut jadi kata kunci
            self._fresh = False
            cur = self.currentText()
            if cur and text != cur and text.startswith(cur):
                text = text[len(cur):]
                le.setText(text)
            elif cur and text != cur and text.endswith(cur):
                text = text[:-len(cur)]
                le.setText(text)
        self._ensure_fonts()
        self._proxy.set_query(text)
        pop = self._comp.popup()
        if self._proxy.rowCount() == 0:
            pop.hide()
            return
        r = self.lineEdit().rect()
        r.setWidth(max(self.width(), 260))
        self._comp.complete(r)
        pop.setCurrentIndex(self._proxy.index(0, 0))

    def _picked(self, text):
        i = self.findText(text or "", Qt.MatchExactly)
        self._comp.popup().hide()
        if i >= 0:
            if i == self.currentIndex():
                self.lineEdit().setText(self.itemText(i))
            self.setCurrentIndex(i)
        else:
            self._revert()
        self.lineEdit().selectAll()

    def _enter(self):
        pop = self._comp.popup()
        if pop.isVisible():
            ix = pop.currentIndex()
            if not ix.isValid() and self._proxy.rowCount():
                ix = self._proxy.index(0, 0)
            if ix.isValid():
                self._picked(ix.data())
                return
        self._revert()

    def _revert(self):
        self._proxy.set_query("")
        self.lineEdit().setText(self.currentText() if self.currentIndex() >= 0 else "")

    def eventFilter(self, obj, ev):
        le = self.lineEdit()
        pop = self._comp.popup()
        if obj is le:
            if ev.type() == QEvent.MouseButtonRelease and self._fresh and not le.hasSelectedText():
                le.selectAll()
        elif obj is pop and ev.type() == QEvent.KeyPress and ev.key() in (Qt.Key_Return, Qt.Key_Enter):
            ix = pop.currentIndex()
            if ix.isValid():
                self._picked(ix.data())
                return True
        elif obj is pop and ev.type() == QEvent.Hide:
            QTimer.singleShot(0, lambda: (not self.hasFocus()) and self._revert())
        return super().eventFilter(obj, ev)

    # QComboBox meneruskan fokus ke kotak ketiknya secara langsung (tanpa event filter), jadi ditangani di sini
    def focusInEvent(self, e):
        super().focusInEvent(e)
        self._fresh = True
        QTimer.singleShot(0, self.lineEdit().selectAll)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        if not self._comp.popup().isVisible():
            self._revert()

    def showPopup(self):
        self._comp.popup().hide()
        self._proxy.set_query("")
        self._ensure_fonts()
        w = max(self.width(), 260)
        self.view().setMinimumWidth(w)
        super().showPopup()
