"""Tangkapan layar tema (dev)."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = str(tmp / "cfg")

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def pages(d):
    out = []
    for i in range(1, 5):
        im = Image.new("RGB", (900, 1280), "white")
        g = ImageDraw.Draw(im)
        for (x0, y0, x1, y1), sh in (((30, 30, 870, 600), 225), ((30, 630, 440, 1250), 200), ((470, 630, 870, 1250), 235)):
            g.rectangle((x0, y0, x1, y1), fill=(sh, sh, sh), outline="black", width=6)
        for bx, by in ((120, 120), (520, 760), (110, 900)):
            g.ellipse((bx, by, bx + 280, by + 160), fill="white", outline="black", width=4)
            g.text((bx + 140, by + 80), "HELLO!", font=ImageFont.truetype(BOLD, 34), fill="black", anchor="mm")
        p = d / f"{i:02d}.png"
        im.save(p)
        out.append(str(p))
    return out


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    from gui import main_window as mw
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui import uifonts
    print("inter", uifonts.load(), flush=True)
    app.setStyleSheet(mw.STYLE)

    def pump(n=300):
        for _ in range(n):
            app.processEvents()

    w = mw.MainWindow()
    w.resize(1500, 900)
    w.show()
    pump()
    w.grab().save(str(out / "1_welcome.png"))
    d = tmp / "ch"
    d.mkdir()
    pages(d)
    w._load_paths([str(d)])
    pump(600)
    from core.models import TextBlock
    p = w.page()
    p.blocks = [TextBlock(x=120, y=120, w=280, h=160, source="HELLO!", translation="HALO!"),
                TextBlock(x=520, y=760, w=280, h=160, source="HELLO!", translation="HAI!", kind="free"),
                TextBlock(x=110, y=900, w=280, h=160, source="[logo judul]", kind="title")]
    w._show_current()
    pump(300)
    w._select(p.blocks[0])
    pump(300)
    w.grab().save(str(out / "2_editor.png"))
    from gui.alert import MessageBox
    QTimer.singleShot(400, lambda: (app.activeModalWidget().grab().save(str(out / "3_alert.png")),
                                    app.activeModalWidget().reject()))
    MessageBox.question(w, "Rexxa Translator", "Simpan perubahan proyek sebelum keluar?")
    from gui.skillsdlg import StoryDialog
    sd = StoryDialog(w.project, w.settings, w)
    sd.resize(980, 560)
    sd.show()
    pump()
    sd.grab().save(str(out / "4_dialog.png"))
    sd.close()
    from gui.exportdlg import ExportDialog
    ed = ExportDialog(w.project, 0, w.settings, w)
    ed.resize(1180, 760)
    ed.show()
    pump(800)
    ed.grab().save(str(out / "5_export.png"))
    print("ok", flush=True)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
