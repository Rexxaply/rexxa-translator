"""Tangkapan layar dialog Kotak judul (dev)."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = str(tmp / "cfg")

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from core.models import Page, Project, TextBlock  # noqa: E402

BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def page(d):
    im = Image.new("RGB", (900, 1300), (18, 14, 30))
    g = ImageDraw.Draw(im)
    for i in range(0, 900, 6):
        g.line((i, 900, i + 300, 1300), fill=(40, 30, 60), width=2)
    f = ImageFont.truetype(BOLD, 96)
    g.text((450, 330), "LEGEND OF", font=f, fill=(255, 200, 60), anchor="mm", stroke_width=4, stroke_fill=(120, 40, 0))
    g.text((450, 450), "THE SKY", font=ImageFont.truetype(BOLD, 130), fill=(255, 140, 40), anchor="mm",
           stroke_width=5, stroke_fill=(120, 40, 0))
    g.ellipse((300, 700, 600, 860), fill="white")
    p = d / "judul.png"
    im.save(p)
    return str(p)


def logo_png(d):
    im = Image.new("RGBA", (900, 300), (0, 0, 0, 0))
    g = ImageDraw.Draw(im)
    g.text((450, 150), "Pahlawan\nLangit", font=ImageFont.truetype(BOLD, 110), fill=(120, 220, 255, 255),
           anchor="mm", align="center", stroke_width=8, stroke_fill=(10, 30, 90, 255))
    p = d / "logo_saya.png"
    im.save(p)
    return str(p)


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui.main_window import STYLE
    app.setStyleSheet(STYLE)
    from gui.titledlg import TitleDialog
    pg = Page(path=page(tmp))
    b = TextBlock(x=120, y=240, w=660, h=290, kind="title", source="[logo judul]", font=BOLD)
    pg.blocks = [b]
    pr = Project(pages=[pg], target_lang="id")

    def snap(name, dlg):
        dlg.resize(1080, 640)
        dlg.show()
        for _ in range(100):
            app.processEvents()
        dlg._render()
        for j in list(dlg._jobs):
            j.wait(20000)
        for _ in range(200):
            app.processEvents()
        dlg.grab().save(str(out / f"{name}.png"))
        print(name, "ok", dlg.status.text(), flush=True)

    d = TitleDialog(pr, pg, b, {})
    d.text.setText("Legenda Langit")
    snap("1_judul_teks", d)
    d2 = TitleDialog(pr, pg, b, {})
    d2._set_image(logo_png(tmp))
    snap("2_judul_gambar", d2)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
