"""Jendela bergaya Liquid Glass + animasi pop-up ala iOS.

GlassDialog   : dialog tanpa bingkai Windows, panel kaca membulat (gradasi gelap transparan, kilau di tepi,
                bayangan lembut), kepala jendela sendiri (judul, keterangan, tombol tutup) yang bisa diseret.
Animasi       : saat muncul panel "mengembang" dari 92% ke 100% dengan pegas lembut + memudar masuk,
                latar aplikasi di belakangnya meredup. Saat ditutup kebalikannya (lebih singkat).
smooth_scroll : roda mouse menggulir dengan meluncur halus (bukan melompat), juga di daftar yang pendek.
"""
from __future__ import annotations

import math

from PySide6.QtCore import (QEasingCurve, QElapsedTimer, QEvent, QObject, QPoint, QPointF, QPropertyAnimation,
                            QRectF, Qt, QTimer)
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (QAbstractScrollArea, QDialog, QHBoxLayout, QLabel, QPushButton, QSizeGrip,
                               QVBoxLayout, QWidget)

RADIUS = 22
MARGIN = 26                    # ruang di sekeliling panel untuk bayangan

GLASS_STYLE = """
QWidget#glassSheet, QWidget#glassSheet QWidget { background: transparent; }
QWidget#glassSheet QScrollArea, QWidget#glassSheet QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QComboBox QAbstractItemView, QComboBox QAbstractItemView QWidget, QMenu { background: #1f2333; color: #eef0f7;
    border: 1px solid rgba(255,255,255,0.12); border-radius: 10px; padding: 4px; selection-background-color: rgba(150,140,235,0.35); }
QListWidget, QTableWidget, QTreeWidget { background: rgba(0,0,0,0.18); border: 1px solid rgba(255,255,255,0.07); border-radius: 12px; }
QLabel#gTitle { font-family: 'Plus Jakarta Sans', 'Inter', sans-serif; font-size: 13pt; font-weight: 800; color: #f2f4fb; }
QLabel#gSub { color: rgba(225,229,242,0.55); font-size: 9pt; }
QPushButton#gClose { min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; padding: 0;
    border-radius: 15px; border: none; color: #dfe3f0; font-size: 13pt;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,0.16), stop:1 rgba(255,255,255,0.05)); }
QPushButton#gClose:hover { background: rgba(255,110,125,0.35); color: white; }
QPushButton#gPrimary { min-height: 34px; padding: 0 22px; border-radius: 17px; border: none; color: white; font-weight: 700;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(111,143,232,0.92), stop:1 rgba(143,120,224,0.92)); }
QPushButton#gPrimary:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7d9cf0, stop:1 #9d86ea); }
QPushButton#gGhost { min-height: 34px; padding: 0 20px; border-radius: 17px; color: #e3e7f3; font-weight: 600;
    border: 1px solid rgba(255,255,255,0.12);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,0.10), stop:1 rgba(255,255,255,0.03)); }
QPushButton#gGhost:hover { background: rgba(255,255,255,0.14); }
"""


def _spring(u: float) -> float:
    """Pegas teredam (0 -> 1) dengan sedikit lewatan ±2%, terasa seperti animasi iOS."""
    if u >= 1.0:
        return 1.0
    return 1 - math.exp(-6.5 * u) * math.cos(7.5 * u)


class _Dim(QWidget):
    """Lapisan gelap di atas jendela utama selama dialog terbuka."""

    def __init__(self, host: QWidget):
        super().__init__(host)
        self.alpha = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(host.rect())
        host.installEventFilter(self)
        self.show()
        self.raise_()

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Resize:
            self.setGeometry(obj.rect())
        return False

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(6, 8, 14, int(150 * self.alpha)))


class GlassDialog(QDialog):
    POP_IN_MS = 420
    POP_OUT_MS = 190

    def __init__(self, parent=None, title: str = "", subtitle: str = "", size=(760, 560), resizable=True):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(title)
        self.setStyleSheet(GLASS_STYLE)
        self.resize(size[0] + 2 * MARGIN, size[1] + 2 * MARGIN)
        self._anim = None            # {"dir": 1|-1, "t0": ms, "pix": QPixmap, "rect": QRect}
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(8)
        self._timer.timeout.connect(self._tick)
        self._dim = None
        self._drag = None
        self._closing = None
        self._popped = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        self.sheet = QWidget()
        self.sheet.setObjectName("glassSheet")
        outer.addWidget(self.sheet)
        v = QVBoxLayout(self.sheet)
        v.setContentsMargins(22, 18, 18, 16)
        v.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(10)
        tl = QVBoxLayout()
        tl.setSpacing(1)
        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("gTitle")
        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setObjectName("gSub")
        self.sub_lbl.setVisible(bool(subtitle))
        tl.addWidget(self.title_lbl)
        tl.addWidget(self.sub_lbl)
        head.addLayout(tl, 1)
        self.head_extra = QHBoxLayout()
        head.addLayout(self.head_extra)
        close = QPushButton("×")
        close.setObjectName("gClose")
        close.setToolTip("Tutup (Esc)")
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.reject)
        head.addWidget(close, 0, Qt.AlignTop)
        v.addLayout(head)
        self._head_h = 54

        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        v.addLayout(self.body, 1)

        self.footer = QHBoxLayout()
        self.footer.setSpacing(8)
        v.addLayout(self.footer)
        if resizable:
            grip = QSizeGrip(self)
            grip.setFixedSize(16, 16)
            grip.setStyleSheet("background: transparent;")
            self._grip = grip
        else:
            self._grip = None

    # ------------------------------------------------------------ gambar panel kaca
    def _panel_rect(self) -> QRectF:
        return QRectF(self.rect()).adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)

    def _paint_glass(self, p: QPainter, r: QRectF):
        # bayangan lembut berlapis
        for i in range(12, 0, -1):
            a = int(5 + (12 - i) * 1.4)
            path = QPainterPath()
            path.addRoundedRect(r.adjusted(-i, -i + 6, i, i + 6), RADIUS + i, RADIUS + i)
            p.fillPath(path, QColor(0, 0, 0, max(0, a - 6)))
        path = QPainterPath()
        path.addRoundedRect(r, RADIUS, RADIUS)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0.0, QColor(34, 38, 56, 246))
        g.setColorAt(0.55, QColor(24, 27, 40, 248))
        g.setColorAt(1.0, QColor(28, 26, 44, 248))
        p.fillPath(path, QBrush(g))
        # cahaya warna logo yang samar di dalam kaca
        p.save()
        p.setClipPath(path)
        for cx, cy, col in ((0.1, 0.0, QColor(95, 130, 230, 46)), (0.95, 1.0, QColor(150, 115, 230, 40))):
            rg = QRadialGradient(QPointF(r.left() + r.width() * cx, r.top() + r.height() * cy), r.width() * 0.55)
            rg.setColorAt(0, col)
            rg.setColorAt(1, QColor(0, 0, 0, 0))
            p.fillRect(r, QBrush(rg))
        # kilau tipis di sepertiga atas
        hl = QLinearGradient(r.topLeft(), QPointF(r.left(), r.top() + 90))
        hl.setColorAt(0, QColor(255, 255, 255, 16))
        hl.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(r, QBrush(hl))
        p.restore()
        # bingkai kilau (terang di kiri atas, redup di tengah)
        rim = QLinearGradient(r.topLeft(), r.bottomRight())
        rim.setColorAt(0.0, QColor(255, 255, 255, 120))
        rim.setColorAt(0.35, QColor(255, 255, 255, 22))
        rim.setColorAt(0.7, QColor(255, 255, 255, 10))
        rim.setColorAt(1.0, QColor(255, 255, 255, 55))
        p.setPen(QPen(QBrush(rim), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(0.6, 0.6, -0.6, -0.6), RADIUS, RADIUS)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        r = self._panel_rect()
        a = self._anim
        if a is None:
            self._paint_glass(p, r)
            return
        u = min(1.0, (self._clock.elapsed() - a["t0"]) / (self.POP_IN_MS if a["dir"] > 0 else self.POP_OUT_MS))
        if a["dir"] > 0:
            scale = 0.92 + 0.08 * _spring(u)
            op = 1 - (1 - min(1.0, u / 0.55)) ** 3
        else:
            e = u * u
            scale = 1.0 - 0.05 * e
            op = 1 - e
        c = r.center()
        p.translate(c)
        p.scale(scale, scale)
        p.translate(-c)
        p.setOpacity(op)
        self._paint_glass(p, r)
        p.drawPixmap(a["rect"].topLeft(), a["pix"])

    # ------------------------------------------------------------ animasi
    def _start(self, direction: int):
        self.layout().activate()
        rect = self.sheet.geometry()
        pix = self.sheet.grab()
        self._anim = {"dir": direction, "t0": 0, "pix": pix, "rect": rect}
        self.sheet.setUpdatesEnabled(False)
        self.sheet.hide()
        self._clock.start()
        self._timer.start()
        self.update()

    def _tick(self):
        a = self._anim
        if a is None:
            self._timer.stop()
            return
        dur = self.POP_IN_MS if a["dir"] > 0 else self.POP_OUT_MS
        u = min(1.0, self._clock.elapsed() / dur)
        if self._dim is not None:
            self._dim.alpha = min(1.0, u * 1.6) if a["dir"] > 0 else 1 - u
            self._dim.update()
        self.update()
        if u >= 1.0:
            self._timer.stop()
            self._anim = None
            if a["dir"] > 0:
                self.sheet.show()
                self.sheet.setUpdatesEnabled(True)
                self.update()
            else:
                self._finish_close()

    def showEvent(self, e):
        super().showEvent(e)
        if self._popped:
            return
        self._popped = True
        host = self.parentWidget().window() if self.parentWidget() is not None else None
        if host is not None and host.isVisible():
            self._dim = _Dim(host)
            pg = host.geometry()            # muncul di tengah jendela utama
            self.move(pg.center() - QPoint(self.width() // 2, self.height() // 2))
        self._start(1)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._grip is not None:
            self._grip.move(self.width() - MARGIN - 18, self.height() - MARGIN - 18)

    def done(self, r):
        if self._closing is not None:
            return
        self._closing = r
        if self._anim is not None:          # masih animasi masuk: langsung balik keluar
            self._timer.stop()
            self._anim = None
            self.sheet.show()
            self.sheet.setUpdatesEnabled(True)
        self._start(-1)

    def _finish_close(self):
        if self._dim is not None:
            self._dim.deleteLater()
            self._dim = None
        r = self._closing
        super().done(r)
        self._closing = None
        self._popped = False
        self.sheet.show()
        self.sheet.setUpdatesEnabled(True)

    # ------------------------------------------------------------ geser jendela lewat kepala
    def mousePressEvent(self, e):
        r = self._panel_rect()
        if e.button() == Qt.LeftButton and r.contains(e.position()) and e.position().y() < r.top() + self._head_h:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag = None
        super().mouseReleaseEvent(e)


# ---------------------------------------------------------------- gulir halus
class _Smooth(QObject):
    """Roda mouse -> bilah gulir meluncur ke tujuan dengan perlambatan (OutCubic, ±220 ms)."""

    def __init__(self, area: QAbstractScrollArea):
        super().__init__(area)
        self.area = area
        self.anims = {}
        self.target = {}
        area.viewport().installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() != QEvent.Wheel or ev.modifiers() & Qt.ControlModifier:
            return False
        d = ev.angleDelta()
        horiz = abs(d.x()) > abs(d.y()) or bool(ev.modifiers() & Qt.ShiftModifier)
        bar = self.area.horizontalScrollBar() if horiz else self.area.verticalScrollBar()
        if bar is None or bar.maximum() <= bar.minimum():
            return False
        delta = (d.x() or d.y()) if horiz else d.y()
        if not delta:
            return False
        step = max(24, bar.singleStep() * 3, bar.pageStep() // 6)
        key = "h" if horiz else "v"
        anim = self.anims.get(key)
        base = self.target.get(key) if anim is not None and anim.state() == QPropertyAnimation.Running else bar.value()
        tgt = max(bar.minimum(), min(bar.maximum(), int(base - delta / 120.0 * step)))
        self.target[key] = tgt
        if anim is None:
            anim = QPropertyAnimation(bar, b"value", self)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            self.anims[key] = anim
        anim.stop()
        anim.setDuration(220)
        anim.setStartValue(bar.value())
        anim.setEndValue(tgt)
        anim.start()
        return True


def smooth_scroll(area: QAbstractScrollArea):
    """Aktifkan gulir halus pada QScrollArea / QListWidget / QTableWidget / QTextEdit."""
    if isinstance(area, QAbstractScrollArea) and not getattr(area, "_smooth", None):
        area._smooth = _Smooth(area)
        from PySide6.QtWidgets import QAbstractItemView
        if isinstance(area, QAbstractItemView):          # daftar: gulir per piksel, bukan per baris
            area.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            area.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    return area


def smooth_all(root: QWidget):
    for a in root.findChildren(QAbstractScrollArea):
        smooth_scroll(a)
