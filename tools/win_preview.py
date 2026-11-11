"""Windows asli: foto layar dropdown & menu untuk memeriksa pojok hitam (dev)."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image, ImageGrab  # noqa: E402
from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox, QMenu, QVBoxLayout, QWidget  # noqa: E402


def pump(app, sec):
    t = time.time()
    while time.time() - t < sec:
        app.processEvents()
        time.sleep(0.01)


def snap(w, name, out, pad=30):
    g = w.frameGeometry()
    box = (g.left() - pad, g.top() - pad, g.right() + pad, g.bottom() + pad)
    im = ImageGrab.grab(bbox=box, all_screens=True)
    im = im.resize((im.width * 3, im.height * 3), Image.NEAREST)
    im.save(out / name)


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    import platform
    print("Windows:", platform.platform(), flush=True)
    from gui import main_window as mw
    from gui.glass import install_popup_fx
    install_popup_fx(app)
    app.setStyleSheet(mw.STYLE)
    host = QWidget()
    host.setObjectName("host")
    host.setStyleSheet("QWidget#host { background: #f2efe8; }")
    host.resize(520, 380)
    host.move(100, 100)
    lay = QVBoxLayout(host)
    cb = QComboBox()
    cb.addItems(["Otomatis", "manga-ocr (Jepang)", "EasyOCR"])
    lay.addWidget(cb)
    lay.addStretch()
    host.show()
    host.raise_()
    host.activateWindow()
    pump(app, 1.0)
    cb.showPopup()
    pump(app, 1.0)
    cont = cb.view().window()
    print("flags:", int(cont.windowFlags()), "translucent:", cont.testAttribute(Qt.WA_TranslucentBackground), flush=True)
    snap(cont, "1_dropdown.png", out)
    cb.hidePopup()
    pump(app, 0.3)
    m = QMenu(host)
    for t in ("Terjemahkan SEMUA halaman", "Hanya OCR", "Render ulang"):
        m.addAction(t)
    m.popup(host.mapToGlobal(QPoint(40, 80)))
    pump(app, 1.0)
    snap(m, "2_menu.png", out)
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "shots")
