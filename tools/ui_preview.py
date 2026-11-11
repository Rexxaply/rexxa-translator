"""Uji kaca frosted + alert Liquid Glass (dev)."""
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
    rng = np.random.default_rng(3)
    for n in range(1, 4):           # halaman berwarna supaya efek kaca terlihat
        im = np.zeros((900, 640, 3), np.uint8)
        for _ in range(14):
            c = tuple(int(x) for x in rng.integers(40, 255, 3))
            cv2.circle(im, (int(rng.integers(0, 640)), int(rng.integers(0, 900))), int(rng.integers(60, 200)), c, -1)
        cv2.ellipse(im, (320, 300), (180, 120), 0, 0, 360, (255, 255, 255), -1)
        cv2.ellipse(im, (320, 300), (180, 120), 0, 0, 360, (0, 0, 0), 4)
        cv2.putText(im, "HALO!", (235, 320), cv2.FONT_HERSHEY_DUPLEX, 2, (0, 0, 0), 4)
        cv2.imwrite(str(d / f"{n:03d}.png"), im)
    w._load_paths([str(d)])
    pump(app, 1.5)
    from gui.alert import Alert
    from gui.dialogs import NameDialog, SettingsDialog

    def show(dlg, name, *extra):
        dlg.show()
        pump(app, 0.7)
        compose(w, *extra, dlg).save(out / name)
        dlg._closing = None
        dlg.done(0)
        pump(app, 0.4)

    show(Alert(w, "Pengaturan", "Simpan perubahan pengaturan?", "Ada pengaturan yang kamu ubah tapi belum disimpan.",
               kind="save", buttons=[("Simpan", "primary", 1), ("Kembali", "neutral", 2),
                                     ("Tutup tanpa simpan", "danger", 3)]), "1_alert_simpan.png")
    show(Alert(w, "Hapus", "Hapus 3 balon terpilih?", "Teks & gaya balon ini akan hilang. Bisa dibatalkan dengan Ctrl+Z.",
               kind="warn", buttons=[("Hapus", "danger", 1), ("Batal", "neutral", 0)]), "2_alert_hapus.png")
    show(Alert(w, "Gagal", "Gagal menerjemahkan halaman 3",
               "LLM error 502: Generation failed on the model's side.\nCoba pindah preset engine dari menu panah "
               "di tombol Terjemahkan.", kind="error"), "3_alert_error.png")
    show(Alert(w, "Selesai", "Export selesai", "18 gambar disimpan ke folder Ch. 007.", kind="success"),
         "4_alert_sukses.png")
    st = SettingsDialog(w.settings, w, project=w.project)
    st.show()
    pump(app, 0.8)
    compose(w, st).save(out / "5_pengaturan_frosted.png")
    nd = NameDialog(st, "Preset baru", "Preset 2", [])
    nd.show()
    pump(app, 0.8)
    compose(w, st, nd).save(out / "6_nama_di_atas_pengaturan.png")
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
