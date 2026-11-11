"""Uji geser teks dengan tombol panah keyboard (dev)."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = str(tmp / "cfg")
from PIL import Image, ImageDraw  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def pump(app, sec):
    t = time.time()
    while time.time() - t < sec:
        app.processEvents()
        time.sleep(0.01)


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    from gui import main_window as mw
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui import uifonts
    uifonts.load()
    app.setStyleSheet(mw.STYLE)
    w = mw.MainWindow()
    w.resize(1300, 820)
    w.show()
    w.activateWindow()
    d = tmp / "ch"
    d.mkdir()
    im = Image.new("RGB", (600, 800), (235, 235, 235))
    ImageDraw.Draw(im).ellipse((120, 180, 480, 460), fill="white", outline="black", width=4)
    im.save(d / "01.png")
    w._load_paths([str(d)])
    pump(app, 1.5)
    from core.models import TextBlock
    p = w.project.pages[0]
    p.blocks = [TextBlock(x=180, y=240, w=240, h=160, kind="bubble", source="x", translation="Geser aku!", clean=False)]
    w._show_current()
    w._schedule_render(now=True)
    pump(app, 4)
    cv = w.cv_src
    item = cv.boxes[0]
    c = cv.mapFromScene(item.sceneBoundingRect().center())
    QTest.mouseClick(cv.viewport(), Qt.LeftButton, Qt.NoModifier, c)
    pump(app, 0.3)
    w.grab().save(str(out / "1_sebelum.png"))
    cv.setFocus()
    for _ in range(5):
        QTest.keyClick(cv, Qt.Key_Right)
    for _ in range(3):
        QTest.keyClick(cv, Qt.Key_Down, Qt.ShiftModifier)
    pump(app, 0.2)
    b = p.blocks[0]
    print("posisi teks: dx =", b.dx, " dy =", b.dy, "(harapan dx=10, dy=30)", flush=True)
    print("kotak tetap:", (b.x, b.y), flush=True)
    w._schedule_render(now=True)
    pump(app, 4)
    w.grab().save(str(out / "2_sesudah.png"))
    w._select(None)
    sv = cv.horizontalScrollBar().value()
    QTest.keyClick(cv, Qt.Key_Left)
    print("tanpa pilihan: dx tetap", b.dx, flush=True)
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
