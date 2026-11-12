"""Tampilan jendela utama Liquid Glass: latar bergradasi lembut, panel kaca mengambang, kolom alat ber-grup
(klik kiri = pakai, klik kanan = pilih isi grup, seperti Photoshop) dan panel properti yang bisa disembunyikan
dengan animasi pegas."""
from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import (QAction, QActionGroup, QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPolygonF, QRadialGradient)
from PySide6.QtWidgets import QFrame, QMenu, QToolButton, QWidget  # noqa: F401

from .icons import icon


class Backdrop(QWidget):
    """Latar jendela: gelap dengan cahaya biru & ungu yang samar (warna logo Rexxa)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chrome")
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

    def paintEvent(self, _e):
        p = QPainter(self)
        r = QRectF(self.rect())
        p.fillRect(r, QColor(16, 18, 26))
        for cx, cy, rad, col in ((0.15, 0.15, 0.55, QColor(90, 125, 220, 46)),
                                 (0.85, 0.85, 0.55, QColor(140, 110, 220, 46)),
                                 (0.55, 0.0, 0.42, QColor(120, 140, 200, 22))):
            g = QRadialGradient(QPointF(r.width() * cx, r.height() * cy), max(r.width(), r.height()) * rad)
            g.setColorAt(0, col)
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.fillRect(r, QBrush(g))


class GlassPanel(QFrame):
    """Panel kaca: isi semi-transparan + kilau tepi. radius=None -> kapsul (setengah tinggi)."""

    def __init__(self, parent=None, radius: float | None = 20, tint: int = 0):
        super().__init__(parent)
        self.radius = radius
        self.tint = tint                       # 0 = kaca terang, 1 = kaca gelap (label kecil di atas gambar)
        self.setAttribute(Qt.WA_StyledBackground, False)

    def _r(self):
        return self.height() / 2 if self.radius is None else self.radius

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = min(self._r(), r.height() / 2)
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        if self.tint:
            g.setColorAt(0, QColor(30, 33, 48, 215))
            g.setColorAt(1, QColor(20, 22, 33, 210))
        else:
            g.setColorAt(0.0, QColor(255, 255, 255, 24))
            g.setColorAt(0.5, QColor(255, 255, 255, 11))
            g.setColorAt(1.0, QColor(255, 255, 255, 15))
        p.fillPath(path, QBrush(g))
        rim = QLinearGradient(r.topLeft(), r.bottomRight())
        rim.setColorAt(0.0, QColor(255, 255, 255, 92))
        rim.setColorAt(0.35, QColor(255, 255, 255, 14))
        rim.setColorAt(0.65, QColor(255, 255, 255, 6))
        rim.setColorAt(1.0, QColor(255, 255, 255, 38))
        p.setPen(QPen(QBrush(rim), 1.0))
        p.drawPath(path)


class GroupToolButton(QToolButton):
    """Tombol alat dengan beberapa pilihan (grup). Klik kiri = pakai pilihan aktif; klik kanan = daftar pilihan.
    variants: [(id, ikon, nama, pintasan)]. Sinyal picked(id) setiap kali alat dipakai / diganti."""
    picked = Signal(str)

    def __init__(self, variants, tip_title: str, parent=None):
        super().__init__(parent)
        self.variants = list(variants)
        self.tip_title = tip_title
        self.current = self.variants[0][0]
        self.setCheckable(True)
        self.setAutoRaise(True)
        self.setIconSize(QSize(18, 18))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda _p: self.show_menu())
        self.clicked.connect(lambda: self.picked.emit(self.current))
        self._apply()

    def _v(self, vid):
        return next(v for v in self.variants if v[0] == vid)

    def _apply(self):
        vid, ico, name, key = self._v(self.current)
        self.setIcon(icon(ico))
        others = ", ".join(v[2] for v in self.variants if v[0] != vid)
        self.setToolTip(f"{name} ({key})" + (f"  ·  klik kanan: {others}" if len(self.variants) > 1 else ""))

    def set_current(self, vid):
        if any(v[0] == vid for v in self.variants):
            self.current = vid
            self._apply()

    def cycle(self):
        """Pintasan ditekan lagi saat alat ini aktif -> pilihan berikutnya di grup."""
        ids = [v[0] for v in self.variants]
        self.set_current(ids[(ids.index(self.current) + 1) % len(ids)])
        return self.current

    def show_menu(self):
        m = QMenu(self)
        m.setObjectName("toolFly")
        if self.tip_title:
            hd = m.addAction(self.tip_title.upper())
            hd.setEnabled(False)
        grp = QActionGroup(m)
        for vid, ico, name, key in self.variants:
            a = QAction(icon(ico), f"{name}\t{key}", m)
            a.setCheckable(True)
            a.setChecked(vid == self.current)
            a.setData(vid)
            grp.addAction(a)
            m.addAction(a)
        m.addSeparator()
        tip = m.addAction("Tahan Shift saat menyeret = persegi / lingkaran")
        tip.setEnabled(False)
        a = m.exec(self.mapToGlobal(QPoint(self.width() + 6, 0)))
        if a is not None and a.data():
            self.set_current(a.data())
            self.setChecked(True)
            self.picked.emit(self.current)

    def paintEvent(self, e):
        super().paintEvent(e)
        if len(self.variants) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(230, 234, 246, 150))
        w, h = self.width(), self.height()
        s = 4.0                                   # segitiga kecil di pojok kanan bawah (penanda grup)
        p.drawPolygon(QPolygonF([QPointF(w - 4, h - 4 - s), QPointF(w - 4, h - 4), QPointF(w - 4 - s, h - 4)]))


def spring(u: float) -> float:
    """Kurva pegas ala iOS (sedikit memantul, lalu diam)."""
    if u >= 1:
        return 1.0
    return 1 - math.exp(-7.5 * u) * math.cos(8.2 * u * 0.92)


class SlidePanel(QWidget):
    """Pembungkus panel samping yang bisa ditutup/dibuka dengan animasi pegas (lebar ikut beranimasi,
    jadi area halaman manga melebar/menyempit bersamaan)."""
    toggled = Signal(bool)
    stepped = Signal()

    def __init__(self, inner: QWidget, width: int, parent=None):
        super().__init__(parent)
        self.inner = inner
        self.full = width
        self.open = True
        inner.setParent(self)
        self.setFixedWidth(width)
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.valueChanged.connect(self._step)
        self._anim.finished.connect(self._done)
        self._from = self._to = width

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.inner.setGeometry(0, 0, self.full, self.height())

    def set_open(self, on: bool, animate: bool = True):
        if on == self.open and self._anim.state() != QVariantAnimation.Running:
            return
        self.open = on
        self._from = self.width()
        self._to = self.full if on else 0
        self.inner.show()
        if not animate:
            self._step(1.0)
            self._done()
            return
        self._anim.stop()
        self._anim.setDuration(460 if on else 360)
        self._anim.setEasingCurve(QEasingCurve.Linear)
        self._anim.start()

    def _step(self, u):
        u = float(u)
        k = spring(u) if self.open else 1 - (1 - u) ** 3
        w = int(round(self._from + (self._to - self._from) * k))
        w = max(0, min(self.full, w))
        self.setFixedWidth(w)
        self.inner.move(0, 0)                  # panel bergeser utuh ke kanan, bagian kanannya keluar layar
        self.inner.setVisible(w > 2)
        self.stepped.emit()

    def _done(self):
        self.setFixedWidth(self.full if self.open else 0)
        self.inner.setVisible(self.open)
        self.toggled.emit(self.open)
