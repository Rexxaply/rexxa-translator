"""Ukur: apakah foto isi Pengaturan sebelum tampil sama dengan isi setelah tampil? (dev)"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = str(tmp / "cfg")
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def pump(app, sec):
    t = time.time()
    while time.time() - t < sec:
        app.processEvents()
        time.sleep(0.004)


def arr(pm):
    q = pm.toImage().convertToFormat(pm.toImage().Format.Format_RGBA8888)
    a = np.frombuffer(q.constBits(), np.uint8).reshape(q.height(), q.bytesPerLine())[:, :q.width() * 4]
    return a.reshape(q.height(), q.width(), 4).copy()


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
    w.show()
    pump(app, 0.8)
    from gui.dialogs import SettingsDialog
    for tab in (0, 1):
        w.settings["_settings_tab"] = tab
        dlg = SettingsDialog(w.settings, w, project=w.project)
        dlg.show()
        print(f"tab {tab}: langsung setelah show -> opasitas jendela={dlg.windowOpacity()} | animasi belum mulai={dlg._anim is None}",
              flush=True)
        while dlg._anim is None:
            app.processEvents()
        before = arr(dlg._anim["pix"])
        r0 = dlg._anim["rect"]
        print(f"tab {tab}: saat animasi mulai -> opasitas={dlg.windowOpacity()}", flush=True)
        pump(app, 1.0)
        after = arr(dlg.sheet.grab())
        r1 = dlg.sheet.geometry()
        same_size = before is not None and before.shape == after.shape
        diff = float(np.abs(before.astype(int) - after.astype(int)).mean()) if same_size else -1
        print(f"tab {tab}: posisi/ukuran isi sebelum={r0} sesudah={r1} | beda piksel rata-rata={diff:.2f}", flush=True)
        if same_size:
            Image.fromarray(np.concatenate([before, after], 1)).save(out / f"beda_tab{tab}.png")
        if tab == 1:
            from PySide6.QtWidgets import QLabel, QLineEdit, QCheckBox
            tl = [x for x in dlg.findChildren((QLabel, QLineEdit, QCheckBox)) if x.toolTip() and x.objectName() != "gHint"]
            hints = [x for x in dlg.findChildren(QLabel) if x.objectName() == "gHint" and x.toolTip()]
            print("label/kolom/centang yang masih punya keterangan:", [x.text()[:20] if hasattr(x, "text") else "" for x in tl],
                  "| ikon (i) berketerangan:", len(hints), flush=True)
        dlg._closing = None
        dlg.done(0)
        pump(app, 0.4)
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
