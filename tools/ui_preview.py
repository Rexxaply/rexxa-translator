"""Uji kecepatan edit teks di aplikasi (dev)."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = str(tmp / "cfg")
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def pump(app, sec):
    t = time.time()
    while time.time() - t < sec:
        app.processEvents()
        time.sleep(0.005)


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
    d = tmp / "ch"
    d.mkdir()
    rng = np.random.default_rng(0)
    img = (rng.random((2400, 1600, 1)) * 40 + 200).astype(np.uint8).repeat(3, 2)
    from core.models import TextBlock
    blocks = []
    for k in range(12):
        x, y = 80 + (k % 3) * 500, 80 + (k // 3) * 580
        cv2.ellipse(img, (x + 200, y + 150), (190, 140), 0, 0, 360, (255, 255, 255), -1)
        cv2.ellipse(img, (x + 200, y + 150), (190, 140), 0, 0, 360, (0, 0, 0), 4)
        blocks.append(TextBlock(x=x + 60, y=y + 60, w=280, h=180, kind="bubble", source="x",
                                translation="Halo, apa kabar?", clean=False))
    cv2.imwrite(str(d / "001.png"), img)
    w._load_paths([str(d)])
    pump(app, 1.5)
    p = w.project.pages[0]
    p.blocks = blocks
    w._show_current()
    w.settings["clean_method"] = "opencv"
    w._schedule_render(now=True)
    while w.thread:
        pump(app, 0.05)
    pump(app, 0.5)
    w._select(p.blocks[4])
    res = []
    for i in range(5):
        t0 = time.time()
        w.e_tr.setPlainText(f"Teks baru nomor {i}!")       # sama seperti mengetik di kolom terjemahan
        while not w.thread:
            pump(app, 0.005)
        while w.thread:
            pump(app, 0.005)
        pump(app, 0.02)
        res.append(round((time.time() - t0) * 1000))
    print("edit -> hasil tampil (ms, termasuk jeda tunggu ketik 250 ms):", res, flush=True)
    from core import detector
    from gui import imgcache as ic
    shown = ic.get(p.output_path)
    detector.flush_writes()
    disk = detector.load_image(p.output_path)
    from PySide6.QtGui import QImage
    q = shown.convertToFormat(QImage.Format.Format_BGR888)
    arr = np.frombuffer(q.constBits(), np.uint8).reshape(q.height(), q.bytesPerLine())[:, :q.width() * 3]
    print("tampilan == file disk:", np.array_equal(arr.reshape(q.height(), q.width(), 3), disk), flush=True)
    w.grab().save(str(out / "1_edit.png"))
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
