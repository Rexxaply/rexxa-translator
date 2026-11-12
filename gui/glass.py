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
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (QAbstractScrollArea, QDialog, QHBoxLayout, QLabel, QPushButton, QSizeGrip,
                               QVBoxLayout, QWidget)

RADIUS = 22
MARGIN = 26                    # ruang di sekeliling panel untuk bayangan

GLASS_STYLE = """
QWidget { background: transparent; }
QScrollArea { border: none; }
QComboBoxPrivateContainer { background: transparent; border: none; }
QComboBox QAbstractItemView { background: transparent;
    border: none; border-radius: 12px; padding: 5px; outline: 0; color: #e3e7f3; }
QComboBox QAbstractItemView::item { min-height: 30px; padding: 2px 10px; border-radius: 8px; margin: 1px 0; }
QComboBox QAbstractItemView::item:hover { background: rgba(255,255,255,0.07); }
QComboBox QAbstractItemView::item:selected { color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(111,143,232,0.62), stop:1 rgba(143,120,224,0.62)); }
QMenu { background: transparent;
    border: none; border-radius: 12px; padding: 6px; }
QMenu::item { padding: 7px 20px 7px 12px; border-radius: 8px; color: #e3e7f3; }
QMenu::item:selected { color: white; background: rgba(140,130,230,0.55); }
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


def _no_os_animation(w):
    """Matikan animasi bawaan Windows saat jendela muncul / hilang (bertabrakan dengan animasi pop-up kita)."""
    import sys
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(w.winId())
        val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 3, ctypes.byref(val), ctypes.sizeof(val))  # TRANSITIONS_FORCEDISABLED
    except Exception:
        pass


def frosted(host, rect=None, sigma: float = 10.0):
    """Ambil gambar `host` (seluruhnya atau area `rect` dalam koordinat host), buramkan & hidupkan warnanya.
    -> (QPixmap | None, titik kiri-atas global). Dipakai latar kaca dialog, menu & dropdown."""
    try:
        import cv2
        import numpy as np
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QImage, QPixmap
        if rect is None:
            rect = host.rect()
        rect = QRect(rect).intersected(host.rect())
        if rect.width() < 4 or rect.height() < 4:
            return None, QPoint()
        shot = host.grab(rect)
        dpr = shot.devicePixelRatio()
        img = shot.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        w, h = img.width(), img.height()
        arr = np.frombuffer(img.constBits(), np.uint8).reshape(h, img.bytesPerLine())[:, :w * 4].reshape(h, w, 4)
        sw, sh = max(1, w // 4), max(1, h // 4)
        small = cv2.resize(arr[:, :, :3], (sw, sh), interpolation=cv2.INTER_AREA)
        small = cv2.GaussianBlur(small, (0, 0), sigma)
        hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.15, 0, 255)       # warna sedikit lebih hidup, khas Liquid Glass
        small = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
        big = np.ascontiguousarray(cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR))
        q = QImage(big.data, w, h, big.strides[0], QImage.Format.Format_RGB888).copy()
        pm = QPixmap.fromImage(q)
        pm.setDevicePixelRatio(dpr)
        return pm, host.mapToGlobal(rect.topLeft())
    except Exception:
        return None, QPoint()


class _Dim(QWidget):
    """Lapisan gelap di atas jendela utama selama dialog terbuka.

    Selama animasi, lapisan ini menggambar FOTO jendela utama + gelap (mode pekat). Dengan begitu tiap frame animasi
    hanya satu drawPixmap — jendela utama di bawahnya tidak ikut digambar ulang 60x per detik (itu yang dulu membuat
    animasi tersendat lalu 'loncat' di PC dengan layar besar). Setelah animasi selesai kembali ke mode transparan."""

    def __init__(self, host: QWidget):
        super().__init__(host)
        self.alpha = 0.0
        self._shot = None
        if not isinstance(host, GlassDialog):
            try:
                self._shot = host.grab()
            except Exception:
                self._shot = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_OpaquePaintEvent, self._shot is not None)
        self.setGeometry(host.rect())
        host.installEventFilter(self)
        self.show()
        self.raise_()

    def live(self):
        """Animasi selesai: lepas foto, gambar gelap transparan di atas jendela asli."""
        if self._shot is not None:
            self._shot = None
            self.setAttribute(Qt.WA_OpaquePaintEvent, False)
            self.update()

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Resize:
            self.setGeometry(obj.rect())
            self.live()
        return False

    def paintEvent(self, _e):
        p = QPainter(self)
        col = QColor(6, 8, 14, int(150 * self.alpha))
        host = self.parentWidget()
        if self._shot is not None:
            p.drawPixmap(0, 0, self._shot)
            p.fillRect(self.rect(), col)
        elif isinstance(host, GlassDialog):          # dialog di atas dialog: redupkan panel kacanya saja
            p.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(host._panel_rect(), RADIUS, RADIUS)
            p.fillPath(path, col)
        else:
            p.fillRect(self.rect(), col)


class GlassDialog(QDialog):
    POP_IN_MS = 420
    POP_OUT_MS = 130

    def __init__(self, parent=None, title: str = "", subtitle: str = "", size=(760, 560), resizable=True,
                 header: bool = True):
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
        self._bd = None              # latar frosted: gambar jendela di belakang yang sudah diburamkan
        self._bd_origin = QPoint()

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
        if header:
            v.addLayout(head)
            self._head_h = 54
        else:
            for w in (self.title_lbl, self.sub_lbl, close):
                w.hide()
            self._head_h = 40

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
        frosted = self._bd is not None
        if frosted:
            # dasar gelap (untuk bagian di luar jendela utama), lalu isi aplikasi yang diburamkan
            p.fillPath(path, QColor(18, 20, 30))
            p.save()
            dev = p.worldTransform().map(path)          # kaca boleh mengecil saat animasi, latar tetap diam
            p.resetTransform()
            p.setClipPath(dev)
            p.drawPixmap(self.mapFromGlobal(self._bd_origin), self._bd)
            p.restore()
        a0, a1 = (214, 224) if frosted else (251, 252)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0.0, QColor(34, 38, 58, a0))
        g.setColorAt(0.55, QColor(22, 25, 38, a1))
        g.setColorAt(1.0, QColor(28, 25, 46, a1))
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

    def _card(self, content: QPixmap | None) -> QPixmap:
        """Seluruh dialog (kaca + isi) dirender SEKALI ke satu gambar; animasi cukup menskalakan gambar ini."""
        dpr = self.devicePixelRatioF()
        pm = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self._paint_glass(p, self._panel_rect())
        if content is not None:
            p.drawPixmap(self.sheet.geometry().topLeft(), content)
        p.end()
        return pm

    def paintEvent(self, _e):
        p = QPainter(self)
        a = self._anim
        if a is None:
            p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
            self._paint_glass(p, self._panel_rect())
            return
        if not a.get("shown"):                     # frame pertama belum boleh terlihat (jendela masih opacity 0)
            a["painted"] = True
        u = a["u"]
        if a["dir"] > 0:
            scale = 0.92 + 0.08 * _spring(u)
            op = 1.0
        else:
            scale = 1.0 - 0.10 * u * u
            op = 1.0 - u * u
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        c = QRectF(self.rect()).center()
        p.translate(c)
        p.scale(scale, scale)
        p.translate(-c)
        p.setOpacity(op)
        p.drawPixmap(0, 0, a["card"])

    # ------------------------------------------------------------ animasi
    # Waktu animasi maju per frame dengan langkah maksimum MAX_STEP_MS. Kalau PC sempat tersendat (mis. Windows
    # menyiapkan jendela baru), animasi berhenti sejenak lalu lanjut mulus — tidak pernah loncat ke akhir.
    MAX_STEP_MS = 34

    def _begin(self, direction: int, card: QPixmap):
        self._anim = {"dir": direction, "u": 0.0, "card": card, "shown": direction < 0, "painted": False}
        self.sheet.setUpdatesEnabled(False)
        self.sheet.hide()
        self._clock.start()
        self._timer.start()

    def _start(self, direction: int):
        self.layout().activate()
        self._begin(direction, self._card(self.sheet.grab()))
        self.update()

    def _tick(self):
        a = self._anim
        if a is None:
            self._timer.stop()
            return
        if not a["shown"]:
            # jendela sudah ada tapi masih tak terlihat: tunggu frame pertamanya benar-benar tergambar,
            # baru dimunculkan. Jadi tidak pernah ada panel setengah jadi di layar.
            if not a["painted"]:
                self.update()
                return
            a["shown"] = True
            self.setWindowOpacity(1.0)
            self._clock.start()
            return
        dt = min(self._clock.restart(), self.MAX_STEP_MS)
        dur = self.POP_IN_MS if a["dir"] > 0 else self.POP_OUT_MS
        a["u"] = u = min(1.0, a["u"] + dt / dur)
        if self._dim is not None:
            self._dim.alpha = min(1.0, u * 2.5) if a["dir"] > 0 else (1 - u) ** 2
            self._dim.update()
        self.update()
        if u >= 1.0:
            self._timer.stop()
            self._anim = None
            if a["dir"] > 0:
                self.sheet.show()
                self.sheet.setUpdatesEnabled(True)
                self.update()
                if self._dim is not None:
                    self._dim.live()
            else:
                self._finish_close()

    def setVisible(self, visible: bool):
        # Urutan tanpa glitch:
        #  1. posisi, latar frosted & lapisan redup disiapkan SEBELUM tampil;
        #  2. tata letak diselesaikan di belakang layar, kaca + isi dirender jadi satu gambar;
        #  3. jendela asli dibuat dengan opacity 0, frame pertamanya digambar tanpa terlihat,
        #     baru dimunculkan & animasi dimulai.
        if visible and not self.isVisible() and not self._popped:
            self._popped = True
            self._prepare_show()
            self._snapshot_offscreen()
            self.setWindowOpacity(0.0)
            super().setVisible(True)
            return
        super().setVisible(visible)

    def _snapshot_offscreen(self):
        from PySide6.QtCore import QCoreApplication
        self.setAttribute(Qt.WA_DontShowOnScreen, True)
        QWidget.setVisible(self, True)                     # tampil "di belakang layar" saja
        QCoreApplication.sendPostedEvents()
        self.layout().activate()
        QCoreApplication.sendPostedEvents()
        content = self.sheet.grab()
        QWidget.setVisible(self, False)
        self.setAttribute(Qt.WA_DontShowOnScreen, False)
        self._begin(1, self._card(content))

    def _prepare_show(self):
        host = self.parentWidget().window() if self.parentWidget() is not None else None
        if host is not None and host.isVisible():
            self._grab_backdrop(host)
            pg = host.geometry()            # muncul di tengah jendela utama
            self.move(pg.center() - QPoint(self.width() // 2, self.height() // 2))
            self._dim = _Dim(host)
        else:                               # belum ada jendela utama: tengah layar
            from PySide6.QtGui import QGuiApplication
            scr = QGuiApplication.primaryScreen()
            if scr is not None:
                self.move(scr.availableGeometry().center() - QPoint(self.width() // 2, self.height() // 2))
        _no_os_animation(self)

    def _grab_backdrop(self, host):
        """Foto jendela di belakang lalu diburamkan (efek kaca frosted). Gagal = kaca biasa."""
        self._bd, self._bd_origin = frosted(host)

    def moveEvent(self, e):
        super().moveEvent(e)
        if self._bd is not None:
            self.update()                       # latar ikut bergeser saat jendela diseret

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
            self.setWindowOpacity(1.0)
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


# ---------------------------------------------------------------- dropdown & menu
def _key(w) -> int:
    """Alamat objek C++ (objek internal Qt seperti wadah dropdown tidak punya pembungkus Python yang tetap)."""
    try:
        import shiboken6
        return int(shiboken6.getCppPointer(w)[0])
    except Exception:
        return id(w)


class _PopupFx(QObject):
    """Semua daftar pilihan (QComboBox) & menu: latar jendela transparan supaya sudut membulat terlihat bersih,
    tanpa bayangan kotak Windows, dan muncul dengan turun halus sedikit (±130 ms)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bd = {}                 # alamat popup -> (latar frosted, titik global)

    @staticmethod
    def _prep(obj):
        """Jadikan jendela popup transparan (sudut lengkung bersih, tanpa pojok hitam) & tanpa bayangan kotak."""
        if obj.property("_rexxa_fx"):
            return
        obj.setProperty("_rexxa_fx", True)
        geo = obj.geometry()                      # posisi sudah dihitung combo / menu: jangan sampai ter-reset
        obj.setAttribute(Qt.WA_TranslucentBackground, True)
        obj.setAttribute(Qt.WA_NoSystemBackground, True)
        # Di Windows, transparansi per piksel HANYA aktif bila jendela juga FramelessWindowHint; tanpa itu area di luar
        # lengkungan digambar hitam. (Mengubah flag membuat ulang jendela -> transparansi pasti aktif.)
        obj.setWindowFlags(obj.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        obj.setGeometry(geo)
        if obj.inherits("QComboBoxPrivateContainer"):
            obj.setContentsMargins(0, 0, 0, 0)

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.Polish and obj.isWidgetType():
            if obj.isWindow() and (obj.inherits("QComboBoxPrivateContainer") or obj.inherits("QMenu")):
                self._prep(obj)
            elif obj.inherits("QComboBox"):
                # siapkan jendela daftar SEJAK kotak dropdown dibuat, jauh sebelum pertama kali dibuka
                try:
                    self._prep(obj.view().window())
                except Exception:
                    pass
        elif t == QEvent.Show and obj.isWidgetType() and obj.property("_rexxa_fx"):
            self._backdrop(obj)
            QTimer.singleShot(0, lambda w=obj: self._appear(w))
            if self._bd.get(_key(obj), (None,))[0] is None:      # dropdown: posisi baru final sesaat setelah tampil
                QTimer.singleShot(0, lambda w=obj: self._retry(w))
        elif t == QEvent.Hide and obj.isWidgetType() and obj.property("_rexxa_fx"):
            self._bd.pop(_key(obj), None)
        elif t == QEvent.Paint and obj.isWidgetType() and obj.property("_rexxa_fx"):
            self._paint_backdrop(obj)             # latar kaca frosted, lalu menu menggambar isinya di atasnya
        return False

    def _retry(self, w):
        try:
            if w.isVisible():
                self._backdrop(w)
                w.update()
                for c in w.findChildren(QWidget):
                    c.update()
        except RuntimeError:
            pass

    @staticmethod
    def _host_of(w):
        from PySide6.QtWidgets import QApplication
        par = w.parentWidget()
        host = par.window() if par is not None else None
        if host is None or host is w or not host.isVisible():
            host = QApplication.activeWindow()
        return host if host is not None and host is not w and host.isVisible() else None

    def _backdrop(self, w):
        host = self._host_of(w)
        if host is None:
            self._bd[_key(w)] = (None, QPoint())
            return
        g = w.geometry()
        tl = host.mapFromGlobal(g.topLeft())
        from PySide6.QtCore import QRect
        self._bd[_key(w)] = frosted(host, QRect(tl.x() - 24, tl.y() - 24, g.width() + 48, g.height() + 48), 5.0)

    def backdrop_of(self, w):
        return self._bd.get(_key(w), (None, QPoint()))[0]

    def _paint_backdrop(self, w):
        """Gambar seluruh panel kaca popup sendiri (latar frosted + warna + garis tepi) dengan lengkungan halus.
        Daftar / menu di atasnya transparan, jadi tidak ada sudut kotak yang menyembul."""
        p = QPainter(w)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(w.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, 12, 12)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(w.rect(), Qt.transparent)              # sudut di luar lengkungan benar-benar kosong
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        bd, origin = self._bd.get(_key(w), (None, QPoint()))
        if bd is not None:
            p.save()
            p.setClipPath(path)
            p.fillPath(path, QColor(22, 25, 37))
            p.drawPixmap(w.mapFromGlobal(origin), bd)
            p.restore()
            top, bot = QColor(44, 50, 74, 165), QColor(26, 29, 44, 185)
        else:                                             # tidak ada jendela di belakang: kaca gelap pekat
            top, bot = QColor(40, 45, 66), QColor(26, 29, 44)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, top)
        g.setColorAt(1, bot)
        p.fillPath(path, QBrush(g))
        p.setPen(QPen(QColor(255, 255, 255, 46), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.end()

    @staticmethod
    def _appear(w):
        try:
            if not w.isVisible():
                return
            end = w.pos()
            # tanpa memudar (memudar membuat isi aplikasi di belakang tembus tajam): cukup turun halus 5 px
            slide = QPropertyAnimation(w, b"pos", w)
            slide.setDuration(130)
            slide.setStartValue(end - QPoint(0, 5))
            slide.setEndValue(end)
            slide.setEasingCurve(QEasingCurve.OutCubic)
            slide.start(QPropertyAnimation.DeleteWhenStopped)
        except Exception:
            try:
                w.setWindowOpacity(1.0)
            except Exception:
                pass


def install_popup_fx(app):
    # Matikan animasi bawaan Windows untuk dropdown & menu (menggulung / memudar). Kalau tidak, dropdown
    # muncul dengan DUA animasi berurutan: efek Windows lalu animasi kaca kita.
    for eff in (Qt.UIEffect.UI_AnimateCombo, Qt.UIEffect.UI_AnimateMenu, Qt.UIEffect.UI_FadeMenu):
        try:
            app.setEffectEnabled(eff, False)
        except Exception:
            pass
    if not getattr(app, "_rexxa_popup_fx", None):
        app._rexxa_popup_fx = _PopupFx(app)
        app.installEventFilter(app._rexxa_popup_fx)
