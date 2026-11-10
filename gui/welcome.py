"""Layar awal (saat belum ada gambar yang dibuka): ajakan membuka gambar / folder / proyek,
atau seret & lepas file langsung ke area ini."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

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
"""


class WelcomeView(QWidget):
    open_images = Signal()
    open_folder = Signal()
    open_project = Signal()
    files_dropped = Signal(list)

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
        v.addStretch(4)

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
