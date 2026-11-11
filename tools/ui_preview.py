"""Rekam buka/tutup Pengaturan per 16 ms di atas halaman berwarna (dev)."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = str(tmp / "cfg")
import time  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def pump(app, sec):
    t = time.time()
    while time.time() - t < sec:
        app.processEvents()
        time.sleep(0.004)


def pil(q):
    q = q.convertToFormat(q.Format.Format_RGBA8888)
    return Image.frombuffer("RGBA", (q.width(), q.height()), bytes(q.constBits()), "raw", "RGBA", q.bytesPerLine(), 1).copy()


def compose(main, *wins):
    base = pil(main.grab().toImage())
    o = main.mapToGlobal(QPoint(0, 0))
    for w in wins:
        if w is not None and w.isVisible():
            p = w.mapToGlobal(QPoint(0, 0)) - o
            base.alpha_composite(pil(w.grab().toImage()), (max(0, p.x()), max(0, p.y())))
    return base.convert("RGB")


class Clock:
    t = 0

    def elapsed(self):
        return self.t

    def start(self):
        self.t = 0


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
    w.resize(1280, 800)
    w.move(0, 0)
    w.show()
    d = tmp / "ch"
    d.mkdir()
    rng = np.random.default_rng(5)
    im = np.full((1300, 900, 3), 235, np.uint8)
    for _ in range(30):
        c = tuple(int(x) for x in rng.integers(30, 255, 3))
        cv2.circle(im, (int(rng.integers(0, 900)), int(rng.integers(0, 1300))), int(rng.integers(40, 160)), c, -1)
    for k in range(8):
        cv2.putText(im, "MANGA", (60, 150 + k * 150), cv2.FONT_HERSHEY_DUPLEX, 4, (20, 20, 20), 9)
    cv2.imwrite(str(d / "001.png"), im)
    w._load_paths([str(d)])
    pump(app, 1.5)
    from gui.dialogs import SettingsDialog
    dlg = SettingsDialog(w.settings, w, project=w.project)
    clk = Clock()
    dlg._clock = clk
    dlg.show()
    while dlg._anim is None:
        app.processEvents()
    dlg._timer.stop()
    frames = []
    for k in range(0, 30):
        clk.t = k * 16
        dlg._tick()
        dlg._timer.stop()
        app.processEvents()
        frames.append(compose(w, dlg))
    while dlg._anim is not None:
        clk.t += 16
        dlg._tick()
    dlg._timer.stop()
    pump(app, 0.2)
    still = compose(w, dlg)
    still.save(out / "3_terbuka.png")
    dlg.reject()
    dlg._timer.stop()
    out_frames = []
    for k in range(0, 12):
        clk.t = k * 16
        if dlg._anim is None:
            break
        dlg._tick()
        dlg._timer.stop()
        app.processEvents()
        if dlg.isVisible():
            out_frames.append(compose(w, dlg))
    sel = [frames[i] for i in (0, 1, 2, 3, 4, 6, 9, 14)]
    sw, sh = 480, 300
    sheet = Image.new("RGB", (sw * 4, sh * 2))
    for i, f in enumerate(sel):
        sheet.paste(f.resize((sw, sh), Image.LANCZOS), ((i % 4) * sw, (i // 4) * sh))
    sheet.save(out / "1_buka_frame.png")
    sel = out_frames[:8]
    sheet = Image.new("RGB", (sw * 4, sh * 2))
    for i, f in enumerate(sel):
        sheet.paste(f.resize((sw, sh), Image.LANCZOS), ((i % 4) * sw, (i // 4) * sh))
    sheet.save(out / "2_tutup_frame.png")
    print("frame buka", len(frames), "frame tutup", len(out_frames), flush=True)
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
