"""Uji folder kerja + export gambar (dev)."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = str(tmp / "cfg")
from PIL import Image, ImageDraw  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def pump(app, sec):
    t = time.time()
    while time.time() - t < sec:
        app.processEvents()
        time.sleep(0.01)


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
    d = tmp / "Ch. 007"
    d.mkdir()
    for n in range(1, 4):
        im = Image.new("RGB", (600, 850), "white")
        ImageDraw.Draw(im).ellipse((150, 200, 450, 420), outline="black", width=4)
        im.save(d / f"{n:03d}.png")
    w._load_paths([str(d)])
    pump(app, 1.5)
    from core import pipeline
    from core.models import TextBlock
    for p in w.project.pages:
        p.blocks = [TextBlock(x=190, y=250, w=220, h=120, kind="bubble", source="Hi", translation="Halo!", clean=False)]
        pipeline.step_render(p, w.project, w.settings, recalc_clean=True)
    print("isi folder chapter:", sorted(x.name for x in d.iterdir()), flush=True)
    print("folder kerja:", Path(w.project.pages[0].output_path).parent.relative_to(tmp), flush=True)
    from gui.exportdlg import ExportDialog
    w.settings["export_opts"] = {"fmt": "img"}
    dlg = ExportDialog(w.project, 0, w.settings, w)
    dlg.r_all.setChecked(True) if hasattr(dlg, "r_all") else None
    dlg.show()
    pump(app, 1.5)
    dlg.grab().save(str(out / "1_export_gambar.png"))
    from core import exporter
    cfg = dlg.config()
    cfg["out"] = str(tmp / "hasil")
    o = cfg.pop("out")
    r = exporter.export(w.project, o, settings=w.settings, **cfg)
    print("export:", r["files"], "file ->", sorted(x.name for x in Path(o).iterdir()), flush=True)
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
