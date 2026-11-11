"""Layar awal (saat belum ada gambar yang dibuka): ajakan membuka gambar / folder / proyek,
atau seret & lepas file langsung ke area ini."""
from __future__ import annotations

import json
import time
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea,
                               QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from .icons import icon

STYLE = """
QWidget#welcome { background: #11141c; }
QLabel#wTitle { font-family: 'Plus Jakarta Sans', 'Inter', 'Segoe UI', sans-serif; color: #e9edf6; font-size: 18pt; font-weight: 800; background: transparent; }
QLabel#wSub { color: #7c84a0; font-size: 10pt; background: transparent; }
QLabel#wHint { color: #56607a; font-size: 8.5pt; background: transparent; }
QPushButton#wBtn { background: #1f2534; color: #d5dbea; border: 1px solid #313849; border-radius: 9px;
                   padding: 0 16px; min-height: 38px; font-weight: 600; }
QPushButton#wBtn:hover { background: #2a3142; border-color: #3d4559; }
QPushButton#wMain { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f86ff, stop:1 #8a63f0); color: white; border: none; border-radius: 9px; font-family: 'Plus Jakarta Sans', 'Inter', 'Segoe UI', sans-serif;
                    padding: 0 18px; min-height: 38px; font-weight: 700; }
QPushButton#wMain:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6596ff, stop:1 #9b78f5); }
QLabel#wSection { font-family: 'Plus Jakarta Sans', 'Inter', 'Segoe UI', sans-serif; color: #9098b0; font-size: 8pt; font-weight: 700; letter-spacing: 1px; background: transparent; }
QToolButton#wClear { color: #6e7690; background: transparent; border: none; font-size: 8.5pt; }
QToolButton#wClear:hover { color: #a598ff; }
QFrame#recentCard { background: #181d29; border: 1px solid #262c3c; border-radius: 10px; }
QFrame#recentCard:hover { background: #1f2534; border-color: #7c6cff; }
QLabel#rName { color: #e9edf6; font-weight: 700; font-size: 9.5pt; background: transparent; }
QLabel#rMeta { color: #7c84a0; font-size: 8pt; background: transparent; }
QLabel#rWhen { color: #a598ff; font-size: 8pt; font-weight: 600; background: transparent; }
QLabel#rThumb { background: #0e1118; border-radius: 6px; }
QScrollArea#recentScroll, QWidget#recentInner { background: transparent; border: none; }
"""


def ago(ts: float, now: float | None = None) -> str:
    """'baru saja', '2 menit yang lalu', '4 jam 39 menit yang lalu', '2 hari yang lalu', ..."""
    d = int(max(0, (now or time.time()) - ts))
    m, h, day = d // 60, d // 3600, d // 86400
    if d < 60:
        return "baru saja"
    if m < 60:
        return f"{m} menit yang lalu"
    if h < 24:
        mm = m % 60
        return f"{h} jam {mm} menit yang lalu" if mm else f"{h} jam yang lalu"
    if day < 7:
        hh = h % 24
        return f"{day} hari {hh} jam yang lalu" if hh and day < 2 else f"{day} hari yang lalu"
    if day < 30:
        return f"{day // 7} minggu yang lalu"
    if day < 365:
        return f"{day // 30} bulan yang lalu"
    return f"{day // 365} tahun yang lalu"


_ago = ago


def project_info(path: str, opened: float | None = None) -> dict | None:
    """Ringkasan file proyek untuk riwayat: jumlah halaman, selesai, gambar sampul, waktu ubah."""
    f = Path(path)
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None
    pages = d.get("pages") or []
    done = sum(1 for p in pages if p.get("status") == "selesai")
    thumb = ""
    for p in pages[:1]:
        for k in ("output_path", "path"):
            if p.get(k) and Path(p[k]).exists():
                thumb = p[k]
                break
    return {"path": str(f), "name": f.stem, "pages": len(pages), "done": done, "thumb": thumb,
            "mtime": f.stat().st_mtime, "folder": str(f.parent), "opened": opened or f.stat().st_mtime,
            "langs": f"{(d.get('source_lang') or '').upper()} → {(d.get('target_lang') or '').upper()}"}


def _thumb(path: str, w: int = 64, h: int = 84) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill(QColor("#0e1118"))
    if not path:
        return pm
    r = QImageReader(path)
    r.setAutoTransform(True)
    sz = r.size()
    if sz.isValid() and sz.width() > 0:
        # ambil bagian atas (webtoon panjang -> tetap terlihat isinya)
        k = w / sz.width()
        r.setScaledSize(QSize(w, max(1, int(sz.height() * k))))
    img = r.read()
    if img.isNull():
        return pm
    p = QPainter(pm)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    src = img.copy(0, 0, img.width(), min(img.height(), int(img.width() * h / w)))
    p.drawImage(QRectF(0, 0, w, h), src)
    p.end()
    return pm


class RecentCard(QFrame):
    clicked = Signal(str)
    remove = Signal(str)

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self.path = info["path"]
        self.setObjectName("recentCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(self.path)
        self.setFixedHeight(104)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 10, 12, 10)
        h.setSpacing(12)
        t = QLabel()
        t.setObjectName("rThumb")
        t.setFixedSize(64, 84)
        t.setPixmap(_thumb(info["thumb"]))
        h.addWidget(t)
        v = QVBoxLayout()
        v.setSpacing(3)
        n = QLabel(info["name"])
        n.setObjectName("rName")
        n.setMinimumWidth(60)
        v.addWidget(n)
        prog = f"{info['done']}/{info['pages']} halaman selesai" if info["pages"] else "belum ada halaman"
        for txt in (f"{prog}  ·  {info['langs']}", info["folder"]):
            m = QLabel(txt)
            m.setObjectName("rMeta")
            m.setMinimumWidth(60)
            m.setTextFormat(Qt.PlainText)
            v.addWidget(m)
        v.addStretch()
        h.addLayout(v, 1)
        self.opened = info.get("opened") or info["mtime"]
        self.when = QLabel()
        self.when.setObjectName("rWhen")
        self.when.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.when.setToolTip("Terakhir dibuka: " + time.strftime("%d %b %Y, %H:%M", time.localtime(self.opened)))
        h.addWidget(self.when)
        self.tick()

    def tick(self):
        self.when.setText("dibuka\n" + ago(self.opened))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.path)
        super().mouseReleaseEvent(e)

    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.addAction("Buka proyek", lambda: self.clicked.emit(self.path))
        m.addAction("Hapus dari riwayat", lambda: self.remove.emit(self.path))
        m.exec(e.globalPos())


class WelcomeView(QWidget):
    open_images = Signal()
    open_folder = Signal()
    open_project = Signal()
    files_dropped = Signal(list)
    open_recent = Signal(str)
    remove_recent = Signal(str)
    clear_recent = Signal()
    MAX_SHOWN = 3              # layar awal: 3 proyek terbaru (semua riwayat ada di menu ikon folder)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("welcome")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(STYLE)
        self.setAcceptDrops(True)
        self._hover = False

        v = QVBoxLayout(self)
        v.addStretch(3)
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        from core.paths import code_dir
        from PySide6.QtGui import QPixmap
        app_icon = code_dir() / "assets" / "icon.png"
        pm = QPixmap(str(app_icon)) if app_icon.exists() else QPixmap()
        if pm.isNull():
            logo.setPixmap(icon("image", "#6e7690", 96).pixmap(QSize(56, 56)))
        else:
            logo.setPixmap(pm.scaled(88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setStyleSheet("background: transparent;")
        v.addWidget(logo)
        v.addSpacing(14)
        t = QLabel("Buka gambar untuk mulai")
        t.setObjectName("wTitle")
        t.setAlignment(Qt.AlignCenter)
        v.addWidget(t)
        s = QLabel("Seret & lepas file atau folder ke sini, atau tekan Ctrl+O")
        s.setObjectName("wSub")
        s.setAlignment(Qt.AlignCenter)
        v.addWidget(s)
        v.addSpacing(22)

        row = QHBoxLayout()
        row.addStretch()
        for text, ic, sig, obj in (("Buka folder chapter", "open", self.open_folder, "wMain"),
                                   ("Buka gambar", "image", self.open_images, "wBtn"),
                                   ("Buka proyek", "project", self.open_project, "wBtn")):
            b = QPushButton("  " + text)
            b.setObjectName(obj)
            b.setIcon(icon(ic, "#ffffff" if obj == "wMain" else "#d5dbea"))
            b.setIconSize(QSize(18, 18))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(sig.emit)
            row.addWidget(b)
            row.addSpacing(6)
        row.addStretch()
        v.addLayout(row)
        v.addSpacing(18)
        h = QLabel("PNG · JPG · WEBP · BMP · proyek .mtproj")
        h.setObjectName("wHint")
        h.setAlignment(Qt.AlignCenter)
        v.addWidget(h)
        v.addSpacing(26)

        # ---- riwayat proyek
        self.recent_box = QWidget()
        self.recent_box.setStyleSheet("background: transparent;")
        rb = QVBoxLayout(self.recent_box)
        rb.setContentsMargins(0, 0, 0, 0)
        rb.setSpacing(8)
        head = QHBoxLayout()
        lab = QLabel("PROYEK TERAKHIR")
        lab.setObjectName("wSection")
        head.addWidget(lab)
        head.addStretch()
        clr = QToolButton(text="Hapus riwayat")
        clr.setObjectName("wClear")
        clr.setCursor(Qt.PointingHandCursor)
        clr.clicked.connect(self.clear_recent.emit)
        head.addWidget(clr)
        rb.addLayout(head)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("recentScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("recentInner")
        self.grid = QGridLayout(inner)
        self.grid.setContentsMargins(0, 0, 4, 0)
        self.grid.setSpacing(10)
        self.scroll.setWidget(inner)
        rb.addWidget(self.scroll, 1)
        wrap = QHBoxLayout()
        wrap.addStretch(1)
        self.recent_box.setMaximumWidth(640)
        self.recent_box.setMinimumWidth(320)
        self.recent_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        wrap.addWidget(self.recent_box, 8)
        wrap.addStretch(1)
        v.addLayout(wrap, 6)
        self.recent_box.hide()
        v.addStretch(2)
        self._recent = []
        from PySide6.QtCore import QTimer
        self._timer = QTimer(self, interval=30_000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_recent(self, paths: list[str], opened: dict | None = None):
        """Isi daftar proyek terakhir, terbaru (terakhir dibuka) di atas. opened = {path: waktu}."""
        if opened is not None:
            self._opened = dict(opened)
        opened = getattr(self, "_opened", {})
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        infos = []
        for p in paths:
            i = project_info(p, opened.get(p))
            if i:
                infos.append(i)
            if len(infos) >= self.MAX_SHOWN:
                break
        self._recent = infos
        cols = 1                              # daftar menurun: terbaru di atas
        self._cards = []
        for n, info in enumerate(infos):
            c = RecentCard(info)
            self._cards.append(c)
            c.clicked.connect(self.open_recent.emit)
            c.remove.connect(self.remove_recent.emit)
            self.grid.addWidget(c, n // cols, n % cols)
        self.recent_box.setVisible(bool(infos))
        rows = (len(infos) + cols - 1) // cols
        self.scroll.setMinimumHeight(min(rows, 3) * 114)
        self._cols = cols

    def _tick(self):
        """Perbarui tulisan 'x menit yang lalu' (dipanggil berkala)."""
        if not self.isVisible():
            return
        for c in getattr(self, "_cards", []):
            try:
                c.tick()
            except RuntimeError:
                pass

    # ---- bingkai putus-putus (menyala saat file diseret ke atasnya)
    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        m = 28
        r = QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)
        if r.width() < 100 or r.height() < 100:
            return
        if self._hover:
            p.fillRect(r, QColor(124, 108, 255, 22))
        pen = QPen(QColor("#7c6cff" if self._hover else "#2d3446"), 1.6, Qt.DashLine)
        pen.setDashPattern([6, 5])
        p.setPen(pen)
        p.drawRoundedRect(r, 16, 16)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            self._hover = True
            self.update()
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._hover = False
        self.update()

    def dropEvent(self, e):
        self._hover = False
        self.update()
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
