"""Uji lencana ikon di kotak pesan (dev)."""
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


def pump(app, sec):
    t = time.time()
    while time.time() - t < sec:
        app.processEvents()
        time.sleep(0.004)


def pil(q):
    q = q.convertToFormat(q.Format.Format_RGBA8888)
    return Image.frombuffer("RGBA", (q.width(), q.height()), bytes(q.constBits()), "raw", "RGBA", q.bytesPerLine(), 1).copy()


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    from gui import main_window as mw
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui import uifonts
    uifonts.load()
    app.setStyleSheet(mw.STYLE)
    from gui.alert import Alert
    items = [("save", "Simpan perubahan pengaturan?", "Ada pengaturan yang kamu ubah tapi belum disimpan.",
              [("Simpan", "primary", 1), ("Kembali", "neutral", 2), ("Tutup tanpa simpan", "danger", 3)]),
             ("warn", "Hapus 3 balon terpilih?", "Bisa dibatalkan dengan Ctrl+Z.", [("Hapus", "danger", 1), ("Batal", "neutral", 0)]),
             ("error", "Gagal menerjemahkan", "LLM error 502 dari penyedia.", None),
             ("success", "Export selesai", "18 gambar disimpan.", None),
             ("info", "Rexxa Translator sudah versi terbaru", "", None),
             ("question", "Jadikan font default sekarang?", "", [("Jadikan default", "primary", 1), ("Nanti", "neutral", 0)])]
    shots = []
    for kind, h, d, b in items:
        a = Alert(None, "Rexxa", h, d, kind=kind, buttons=b)
        a.show()
        pump(app, 0.7)
        im = pil(a.grab().toImage())
        bg = Image.new("RGBA", im.size, (24, 28, 40, 255))
        bg.alpha_composite(im)
        shots.append(bg.convert("RGB"))
        a._closing = None
        a.done(0)
        pump(app, 0.3)
    W = max(s.width for s in shots)
    cols = 2
    rows = (len(shots) + 1) // 2
    H = max(s.height for s in shots)
    sheet = Image.new("RGB", (W * cols, H * rows), (24, 28, 40))
    for i, s in enumerate(shots):
        sheet.paste(s, ((i % cols) * W + (W - s.width) // 2, (i // cols) * H + (H - s.height) // 2))
    sheet.save(out / "lencana.png")
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
