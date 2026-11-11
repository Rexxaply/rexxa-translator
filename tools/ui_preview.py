"""Uji tab Data: hasil kerja per chapter (dev)."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = str(tmp / "cfg")
from PySide6.QtWidgets import QApplication, QTabWidget  # noqa: E402


def pump(app, sec):
    t = time.time()
    while time.time() - t < sec:
        app.processEvents()
        time.sleep(0.01)


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    from core import paths
    seri = tmp / "Reincarnated as a Villainous Duke"
    data = [("Ch. 007.2 - Claria (Part 2)", 0, 18), ("Ch. 007.1 - Claria (Part 1)", 3, 20),
            ("Ch. 006", 12, 22), ("Ch. 005", 41, 19)]
    for name, days, pages in data:
        d = paths.work_dir(str(seri / name / "001.png"))
        for i in range(pages):
            (d / f"{i:03d}.png").write_bytes(os.urandom(150_000))
        t = time.time() - days * 86400
        os.utime(d / ".used", (t, t))
    from gui import main_window as mw
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui import uifonts
    uifonts.load()
    app.setStyleSheet(mw.STYLE)
    w = mw.MainWindow()
    w.resize(1200, 800)
    from gui.dialogs import SettingsDialog
    d = SettingsDialog(w.settings, w, project=w.project)
    tw = d.findChild(QTabWidget)
    for i in range(tw.count()):
        if tw.tabText(i) == "Data":
            tw.setCurrentIndex(i)
    d.resize(760, 760)
    d.show()
    pump(app, 1.0)
    d.data.work_list.item(3).setCheckState(__import__("PySide6.QtCore").QtCore.Qt.Checked)
    pump(app, 0.3)
    d.grab().save(str(out / "1_data_tab.png"))
    from core import datastore as DS
    print("otomatis 30 hari:", DS.auto_cleanup(30), [x["name"] for x in DS.work_dirs()], flush=True)
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
