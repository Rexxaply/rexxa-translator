"""Uji pojok dropdown & menu: harus transparan, bukan hitam (dev)."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["QT_SCALE_FACTOR"] = "2"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = str(tmp / "cfg")
from PIL import Image  # noqa: E402
from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox, QMenu, QVBoxLayout, QWidget  # noqa: E402


def pump(app, sec):
    t = time.time()
    while time.time() - t < sec:
        app.processEvents()
        time.sleep(0.004)


def pil(q):
    q = q.convertToFormat(q.Format.Format_RGBA8888)
    return Image.frombuffer("RGBA", (q.width(), q.height()), bytes(q.constBits()), "raw", "RGBA", q.bytesPerLine(), 1).copy()


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    from gui import main_window as mw
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui import uifonts
    uifonts.load()
    from gui.glass import install_popup_fx
    install_popup_fx(app)
    app.setStyleSheet(mw.STYLE)
    host = QWidget()
    host.setStyleSheet("background: #e8e2d6;")       # latar terang supaya pojok hitam kelihatan
    host.resize(500, 360)
    lay = QVBoxLayout(host)
    cb = QComboBox()
    cb.addItems(["Balon (OpenCV, cepat)", "EasyOCR (teks di mana saja)", "Hybrid (balon + teks bebas)"])
    lay.addWidget(cb)
    lay.addStretch()
    host.show()
    pump(app, 0.5)
    cont = cb.view().window()
    from PySide6.QtCore import Qt
    print("dropdown disiapkan sebelum dibuka:", bool(cont.property("_rexxa_fx")), "| transparan:",
          cont.testAttribute(Qt.WA_TranslucentBackground), flush=True)
    fx = app._rexxa_popup_fx
    cnt = {"n": 0}
    orig = fx._paint_backdrop

    def counted(w):
        cnt["n"] += 1
        return orig(w)
    fx._paint_backdrop = counted
    cb.showPopup()
    pump(app, 0.6)
    print("panggilan gambar panel:", cnt["n"], "| backdrop:", fx.backdrop_of(cont) is not None, flush=True)
    from PySide6.QtGui import QPainter, QColor
    from PySide6.QtCore import QEvent, QObject

    class Probe(QObject):
        def eventFilter(self, o, e):
            if e.type() == QEvent.Paint and o is cont:
                print("  paint container, rect=", e.rect(), flush=True)
            return False
    pr = Probe()
    app.installEventFilter(pr)
    cont.repaint()
    pump(app, 0.1)
    im0 = pil(cont.grab().toImage())
    print("setelah repaint, piksel tengah:", im0.getpixel((im0.width // 2, im0.height - 6)), flush=True)
    # coba: lukis langsung tanpa anak (sembunyikan view sebentar)
    cb.view().hide()
    im1 = pil(cont.grab().toImage())
    print("tanpa view, piksel tengah:", im1.getpixel((im1.width // 2, im1.height // 2)), flush=True)
    cb.view().show()
    im = pil(cont.grab().toImage())
    w, h = im.size
    corners = [im.getpixel((1, 1)), im.getpixel((w - 2, 1)), im.getpixel((1, h - 2)), im.getpixel((w - 2, h - 2))]
    mid = im.getpixel((w // 2, 3))
    print("pojok (RGBA):", corners, "| tepi atas tengah:", mid, flush=True)
    base = pil(host.grab().toImage())
    o = host.mapToGlobal(QPoint(0, 0))
    p = cont.mapToGlobal(QPoint(0, 0)) - o
    base.alpha_composite(im, (max(0, p.x() * 2), max(0, p.y() * 2)))
    base.convert("RGB").save(out / "1_dropdown_latar_terang.png")
    cb.hidePopup()
    m = QMenu(host)
    for t in ("Terjemahkan SEMUA halaman", "Hanya OCR", "Render ulang"):
        m.addAction(t)
    m.popup(host.mapToGlobal(QPoint(20, 60)))
    pump(app, 0.5)
    im = pil(m.grab().toImage())
    w, h = im.size
    print("menu pojok (RGBA):", [im.getpixel((1, 1)), im.getpixel((w - 2, h - 2))], flush=True)
    base = pil(host.grab().toImage())
    p = m.mapToGlobal(QPoint(0, 0)) - o
    base.alpha_composite(im, (max(0, p.x() * 2), max(0, p.y() * 2)))
    base.convert("RGB").save(out / "2_menu_latar_terang.png")
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
