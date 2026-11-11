"""Uji animasi tombol simpan (dev)."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = str(tmp / "cfg")
from PIL import Image  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


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
    w.resize(1300, 800)
    w.show()
    d = tmp / "ch"
    d.mkdir()
    Image.new("RGB", (600, 800), "white").save(d / "01.png")
    w._load_paths([str(d)])
    for _ in range(300):
        app.processEvents()
    w.project.file = str(tmp / "x.mtproj")
    w.project.pages[0].blocks = []
    from core.models import TextBlock
    w.project.pages[0].blocks.append(TextBlock(x=10, y=10, w=50, h=50, translation="A"))
    w._refresh_state()
    print("dirty", w._dirty, "enabled", w.b_save.isEnabled(), flush=True)
    t0 = time.time()
    ok = w.save_project()
    print("saved", ok, "anim", w._save_anim is not None, flush=True)
    shots = []
    k = 0
    while time.time() - t0 < 1.6:
        app.processEvents()
        if time.time() - t0 > k * 0.12:
            g = w.b_save.grab()
            shots.append(g)
            k += 1
        if w._save_anim is None and "stop" not in locals():
            stop = time.time() - t0
            print("berhenti setelah", round(stop, 2), "detik", flush=True)
    print("anim akhir", w._save_anim, "dirty", w._dirty, "enabled", w.b_save.isEnabled(), flush=True)
    sheet = None
    from PySide6.QtGui import QPainter, QPixmap
    W = sum(s.width() + 6 for s in shots)
    pm = QPixmap(W, shots[0].height())
    pm.fill()
    p = QPainter(pm)
    x = 0
    for s in shots:
        p.drawPixmap(x, 0, s)
        x += s.width() + 6
    p.end()
    pm.scaled(pm.width() * 2, pm.height() * 2).save(str(out / "1_save_frames.png"))
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
