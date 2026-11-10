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
QWidget#welcome { background: #141519; }
QLabel#wTitle { color: #e9eaee; font-size: 17pt; font-weight: 700; background: transparent; }
QLabel#wSub { color: #7d818d; font-size: 10pt; background: transparent; }
QLabel#wHint { color: #555966; font-size: 8.5pt; background: transparent; }
QPushButton#wBtn { background: #22242b; color: #d6d8de; border: 1px solid #30333c; border-radius: 9px;
                   padding: 0 16px; min-height: 38px; font-weight: 600; }
QPushButton#wBtn:hover { background: #2a2d35; border-color: #3d414c; }
QPushButton#wMain { background: #ff4d6d; color: white; border: none; border-radius: 9px;
                    padding: 0 18px; min-height: 38px; font-weight: 700; }
QPushButton#wMain:hover { background: #ff6b85; }
QLabel#wSection { color: #8f93a0; font-size: 8pt; font-weight: 700; letter-spacing: 1px; background: transparent; }
QToolButton#wClear { color: #6f7380; background: transparent; border: none; font-size: 8.5pt; }
QToolButton#wClear:hover { color: #ff8a9b; }
QFrame#recentCard { background: #1b1c22; border: 1px solid #272930; border-radius: 10px; }
QFrame#recentCard:hover { background: #22242b; border-color: #ff4d6d; }
QLabel#rName { color: #e9eaee; font-weight: 700; font-size: 9.5pt; background: transparent; }
QLabel#rMeta { color: #7d818d; font-size: 8pt; background: transparent; }
QLabel#rThumb { background: #111214; border-radius: 6px; }
QScrollArea#recentScroll, QWidget#recentInner { background: transparent; border: none; }
"""


def _ago(ts: float) -> str:
    d = max(0, time.time() - ts)
    if d < 60:
        return "baru saja"
    if d < 3600:
        return f"{int(d // 60)} menit lalu"
    if d < 86400:
        return f"{int(d // 3600)} jam lalu"
    if d < 86400 * 30:
        return f"{int(d // 86400)} hari lalu"
    return time.strftime("%d %b %Y", time.localtime(ts))


def project_info(path: str) -> dict | None:
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
            "mtime": f.stat().st_mtime, "folder": str(f.parent),
            "langs": f"{(d.get('source_lang') or '').upper()} → {(d.get('target_lang') or '').upper()}"}


def _thumb(path: str, w: int = 64, h: int = 84) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill(QColor("#111214"))
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
        for txt in (prog, f"{info['langs']}  ·  diubah {_ago(info['mtime'])}", info["folder"]):
            m = QLabel(txt)
            m.setObjectName("rMeta")
            m.setMinimumWidth(60)
            m.setTextFormat(Qt.PlainText)
            v.addWidget(m)
        v.addStretch()
        h.addLayout(v, 1)

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
    open_recent = Signal(str)
    remove_recent = Signal(str)
    clear_recent = Signal()

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
        logo.setPixmap(icon("image", "#6f7380", 96).pixmap(QSize(56, 56)))
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
            b.setIcon(icon(ic, "#ffffff" if obj == "wMain" else "#d6d8de"))
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
        self.recent_box.setMaximumWidth(860)
        self.recent_box.setMinimumWidth(320)
        self.recent_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        wrap.addWidget(self.recent_box, 8)
        wrap.addStretch(1)
        v.addLayout(wrap, 6)
        self.recent_box.hide()
        v.addStretch(2)
        self._recent = []

    def set_recent(self, paths: list[str]):
        """Isi daftar proyek terakhir (file yang sudah tidak ada dilewati)."""
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        infos = [i for i in (project_info(p) for p in paths[:12]) if i]
        self._recent = infos
        cols = 2 if self.width() >= 700 else 1
        for n, info in enumerate(infos):
            c = RecentCard(info)
            c.clicked.connect(self.open_recent.emit)
            c.remove.connect(self.remove_recent.emit)
            self.grid.addWidget(c, n // cols, n % cols)
        self.recent_box.setVisible(bool(infos))
        rows = (len(infos) + cols - 1) // cols
        self.scroll.setMinimumHeight(min(rows, 2) * 114)
        self._cols = cols

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cols = 2 if self.width() >= 700 else 1
        if self._recent and cols != getattr(self, "_cols", cols):
            self.set_recent([i["path"] for i in self._recent])

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
            p.fillRect(r, QColor(255, 77, 109, 18))
        pen = QPen(QColor("#ff4d6d" if self._hover else "#2c2f37"), 1.6, Qt.DashLine)
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
