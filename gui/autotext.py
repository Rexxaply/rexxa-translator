"""Kotak teks yang tingginya mengikuti isi: 1 baris = kotak kecil, bertambah sampai `max_lines` baris,
lebih dari itu bisa digulir (halus, per piksel). Perubahan tinggi beranimasi lembut."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Qt, QVariantAnimation
from PySide6.QtWidgets import QSizePolicy, QTextEdit


class AutoText(QTextEdit):
    def __init__(self, min_lines: int = 1, max_lines: int = 3, parent=None):
        super().__init__(parent)
        self.min_lines, self.max_lines = min_lines, max_lines
        self.setAcceptRichText(False)
        self.setTabChangesFocus(True)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.document().setDocumentMargin(3)
        self._h = 0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(lambda v: self.setFixedHeight(int(v)))
        self.document().documentLayout().documentSizeChanged.connect(lambda _s: self._fit())
        self._fit(animate=False)

    # ------------------------------------------------------------ ukuran
    def set_lines(self, min_lines: int, max_lines: int):
        self.min_lines, self.max_lines = min_lines, max_lines
        self._fit(animate=False)

    def _chrome_h(self) -> int:
        m = self.contentsMargins()
        vm = self.viewportMargins()
        return m.top() + m.bottom() + vm.top() + vm.bottom() + 2 * self.frameWidth()

    def _target(self) -> tuple[int, bool]:
        ls = self.fontMetrics().lineSpacing()
        dm = int(self.document().documentMargin() * 2)
        doc_h = int(self.document().size().height() + 0.5)
        lo = self.min_lines * ls + dm
        hi = self.max_lines * ls + dm
        content = max(lo, doc_h)
        return min(content, hi) + self._chrome_h() + 2, content > hi + 1

    def _fit(self, animate: bool = True):
        h, overflow = self._target()
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if overflow else Qt.ScrollBarAlwaysOff)
        if h == self._h:
            return
        start = self.height() if self._h else h
        self._h = h
        self._anim.stop()
        if animate and self.isVisible() and abs(start - h) > 1:
            self._anim.setStartValue(start)
            self._anim.setEndValue(h)
            self._anim.start()
        else:
            self.setFixedHeight(h)
        if not overflow:
            self.verticalScrollBar().setValue(0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if e.oldSize().width() != e.size().width():     # lebar berubah = jumlah baris (bungkus) berubah
            self._fit(animate=False)

    def showEvent(self, e):
        super().showEvent(e)
        self._fit(animate=False)

    def setPlainText(self, text):
        super().setPlainText(text)
        self._fit(animate=False)

