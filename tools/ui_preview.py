"""Uji: Pengaturan & kotak pesan muncul tanpa frame liar (dev)."""
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
from PySide6.QtCore import QEvent, QObject  # noqa: E402
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


class Spy(QObject):
    """Catat setiap kali jendela dialog digambar & apakah isinya (sheet) terlihat saat itu."""

    def __init__(self, dlg):
        super().__init__()
        self.dlg, self.paints = dlg, []
        dlg.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Paint:
            self.paints.append((self.dlg._anim is not None, self.dlg.sheet.isVisible()))
        return False


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
    from gui.alert import Alert
    for rnd in range(3):
        for tab in (0, 1):
            w.settings["_settings_tab"] = tab
            dlg = SettingsDialog(w.settings, w, project=w.project)
            spy = Spy(dlg)
            dlg.show()
            before = arr(dlg._anim["pix"]) if dlg._anim else None
            pump(app, 0.9)
            after = arr(dlg.sheet.grab())
            diff = float(np.abs(before.astype(int) - after.astype(int)).mean()) if before is not None and before.shape == after.shape else -1
            liar = [p for p in spy.paints[:3] if not p[0]]
            print(f"putaran {rnd} tab {tab}: beda foto={diff:.2f} | gambar pertama saat animasi={spy.paints[0][0] if spy.paints else None}"
                  f" | gambar tanpa animasi di awal={len(liar)} | terbuka={dlg.isVisible()}", flush=True)
            dlg._closing = None
            dlg.done(0)
            pump(app, 0.4)
            print(f"   ditutup={not dlg.isVisible()}", flush=True)
    a = Alert(w, "Tes", "Hapus balon?", "Bisa dibatalkan.", kind="warn", buttons=[("Hapus", "danger", 1), ("Batal", "neutral", 0)])
    spy = Spy(a)
    a.show()
    pump(app, 0.7)
    print("alert: gambar pertama saat animasi =", spy.paints[0][0] if spy.paints else None, "| isi tampil =", a.sheet.isVisible(), flush=True)
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
