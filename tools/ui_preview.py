"""Rekam animasi tombol simpan (dev)."""
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
    w.resize(1000, 700)
    w.show()
    d = tmp / "ch"
    d.mkdir()
    Image.new("RGB", (600, 800), "white").save(d / "01.png")
    w._load_paths([str(d)])
    for _ in range(200):
        app.processEvents()
    w.project.file = str(tmp / "x.mtproj")
    from core.models import TextBlock
    w.project.pages[0].blocks = [TextBlock(x=10, y=10, w=50, h=50, translation="A")]
    w._refresh_state()
    frames = []
    t0 = time.time()
    w.save_project()
    stop = None
    nxt = 0.0
    while time.time() - t0 < 2.8:
        app.processEvents()
        el = time.time() - t0
        if el >= nxt:
            img = w.b_save.grab().toImage()
            ptr = img.constBits()
            pil = Image.frombuffer("RGBA", (img.width(), img.height()), bytes(ptr), "raw", "BGRA", img.bytesPerLine(), 1)
            frames.append(pil.convert("RGB"))
            nxt += 0.02
        if w._save_anim is None and stop is None:
            stop = el
    print("berhenti setelah", round(stop or -1, 2), "detik, frame", len(frames), flush=True)
    big = [f.resize((f.width * 3, f.height * 3), Image.LANCZOS) for f in frames]
    big[0].save(out / "save_anim.gif", save_all=True, append_images=big[1:] + [big[-1]] * 15, duration=20, loop=0)
    strip = Image.new("RGB", (sum(f.width + 4 for f in frames[::3]), frames[0].height), "#131722")
    x = 0
    for f in frames[::3]:
        strip.paste(f, (x, 0))
        x += f.width + 4
    strip.save(out / "strip.png")
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
