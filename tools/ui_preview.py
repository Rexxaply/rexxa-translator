"""Uji pilihan ganda Ctrl+klik (dev)."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = str(tmp / "cfg")
os.environ["APPDATA"] = str(tmp / "cfg")
from PIL import Image, ImageDraw  # noqa: E402
from PySide6.QtCore import QPoint, Qt  # noqa: E402
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
    w.resize(1400, 860)
    w.show()
    d = tmp / "ch"
    d.mkdir()
    im = Image.new("RGB", (600, 800), (235, 235, 235))
    dr = ImageDraw.Draw(im)
    boxes = [(40, 40, 230, 170), (330, 60, 560, 180), (60, 300, 260, 420), (320, 330, 560, 470), (150, 560, 450, 720)]
    for (x0, y0, x1, y1) in boxes:
        dr.ellipse((x0, y0, x1, y1), fill="white", outline="black", width=3)
    im.save(d / "01.png")
    w._load_paths([str(d)])
    pump(app, 1.5)
    from core.models import TextBlock
    p = w.project.pages[0]
    texts = ["Halo semuanya!", "Kamu kenapa sih?", "Aku nggak tahu…", "Ayo cepetan!", "Tunggu aku dong!"]
    p.blocks = [TextBlock(x=x0 + 25, y=y0 + 20, w=x1 - x0 - 50, h=y1 - y0 - 40, kind="bubble",
                          source=t, translation=t, clean=False) for (x0, y0, x1, y1), t in zip(boxes, texts)]
    w._show_current()
    pump(app, 0.5)
    cv = w.cv_src

    def click(b, ctrl):
        item = next(x for x in cv.boxes if x.block is b)
        c = cv.mapFromScene(item.sceneBoundingRect().center())
        QTest.mouseClick(cv.viewport(), Qt.LeftButton, Qt.ControlModifier if ctrl else Qt.NoModifier, c)
        pump(app, 0.2)

    click(p.blocks[0], False)
    click(p.blocks[1], True)
    click(p.blocks[3], True)
    print("dipilih:", [p.blocks.index(b) + 1 for b in w._targets()], "aktif:", p.blocks.index(w.sel) + 1, flush=True)
    w.grab().save(str(out / "1_tiga_dipilih.png"))
    # ubah ukuran teks & rata kiri & warna -> berlaku untuk semua
    w.p_size.setValue(30)
    w._set_align("left")
    w._snap()
    for t in w._targets():
        t.color = "#d62f6b"
    w._load_props(w.sel)
    w._equal_box_size()
    pump(app, 0.3)
    print("ukuran font:", [b.font_size for b in p.blocks], flush=True)
    print("rata:", [b.align for b in p.blocks], flush=True)
    print("ukuran kotak:", [(b.w, b.h) for b in p.blocks], flush=True)
    w._schedule_render(now=True)
    pump(app, 8)
    w.grab().save(str(out / "2_hasil.png"))
    # Ctrl+klik lagi = lepas
    click(p.blocks[1], True)
    print("setelah lepas #2:", [p.blocks.index(b) + 1 for b in w._targets()], flush=True)
    click(p.blocks[4], False)
    print("klik biasa #5:", [p.blocks.index(b) + 1 for b in w._targets()], "bar:", w.multi_bar.isVisible(), flush=True)
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
