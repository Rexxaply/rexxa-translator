"""Uji konfirmasi simpan saat menutup Pengaturan (dev)."""
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
from PySide6.QtCore import QPoint, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402


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
    pump(app, 0.8)
    from gui.dialogs import SettingsDialog
    from gui.alert import Alert

    def alerts():
        return [x for x in QApplication.topLevelWidgets() if isinstance(x, Alert) and x.isVisible()]

    def click_later(label, shot=None):
        def go():
            a = alerts()
            if not a:
                QTimer.singleShot(100, go)
                return
            if shot:
                pump(app, 0.3)
                compose(w, dlg, a[0]).save(out / shot)
            for b in a[0].findChildren(QPushButton):
                if b.text() == label:
                    b.click()
        QTimer.singleShot(300, go)

    # 1) tanpa perubahan -> langsung tutup
    dlg = SettingsDialog(w.settings, w, project=w.project)
    dlg.show()
    pump(app, 0.6)
    print("tanpa perubahan, changed() =", dlg.changed(), flush=True)
    dlg.reject()
    pump(app, 0.5)
    print("tanpa perubahan -> tertutup:", not dlg.isVisible(), "| ada alert:", bool(alerts()), flush=True)

    # 2) ubah lalu tutup -> alert, pilih Kembali
    dlg = SettingsDialog(w.settings, w, project=w.project)
    dlg.show()
    pump(app, 0.6)
    dlg.detect.setCurrentIndex(2)
    dlg.temp.setValue(0.8)
    print("setelah diubah, changed() =", dlg.changed(), flush=True)
    click_later("Kembali", "1_konfirmasi.png")
    dlg.reject()
    pump(app, 0.5)
    print("pilih Kembali -> pengaturan masih terbuka:", dlg.isVisible(), "| deteksi tetap:", dlg.detect.currentData(),
          flush=True)

    # 3) tutup lagi -> Simpan
    res = {}
    dlg.finished.connect(lambda r: res.setdefault("r", r))
    click_later("Simpan")
    dlg.reject()
    pump(app, 0.6)
    print("pilih Simpan -> hasil dialog:", res.get("r"), "(1 = disimpan) | deteksi:",
          dlg.result_settings()["detect_mode"], flush=True)

    # 4) ubah -> Tutup tanpa simpan
    dlg = SettingsDialog(w.settings, w, project=w.project)
    dlg.show()
    pump(app, 0.6)
    dlg.model.setText("model-lain")
    res = {}
    dlg.finished.connect(lambda r: res.setdefault("r", r))
    click_later("Tutup tanpa simpan")
    dlg.reject()
    pump(app, 0.6)
    print("pilih Tutup tanpa simpan -> hasil dialog:", res.get("r"), "(0 = dibuang)", flush=True)
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
