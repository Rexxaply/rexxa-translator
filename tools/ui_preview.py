"""Tangkapan layar dialog Export As (dev): QT_QPA_PLATFORM=offscreen python tools/ui_preview.py out_dir"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from core.models import Page, Project  # noqa: E402


def font(n):
    try:
        return ImageFont.load_default(size=n)
    except TypeError:
        return ImageFont.load_default()


def manga_page(i, d):
    im = Image.new("RGB", (1000, 1420), "white")
    g = ImageDraw.Draw(im)
    for (x0, y0, x1, y1), sh in (((40, 40, 960, 520), 225), ((40, 550, 480, 1380), 205), ((510, 550, 960, 1380), 235)):
        g.rectangle((x0, y0, x1, y1), fill=(sh, sh, sh), outline="black", width=6)
        for k in range(x0 + 20, x1 - 20, 40):
            g.line((k, y1 - 120, k + 60, y1 - 20), fill=(150, 150, 150), width=3)
    for (bx, by) in ((150, 120), (600, 680), (120, 900)):
        g.ellipse((bx, by, bx + 300, by + 170), fill="white", outline="black", width=4)
        g.text((bx + 150, by + 85), f"HALAMAN {i}!", fill="black", font=font(34), anchor="mm")
    g.text((960, 1405), str(i), fill="black", font=font(22), anchor="rm")
    p = d / f"m{i:02d}.png"
    im.save(p)
    return str(p)


def webtoon_page(i, d):
    im = Image.new("RGB", (720, 2200), (250, 246, 240))
    g = ImageDraw.Draw(im)
    cols = [(255, 214, 165), (189, 224, 254), (205, 180, 219), (202, 255, 191)]
    for k, y in enumerate((80, 1150)):
        g.rounded_rectangle((30, y, 690, y + 900), 18, fill=cols[(i + k) % 4], outline=(40, 40, 40), width=4)
        g.ellipse((150, y + 120, 570, y + 380), fill="white", outline=(30, 30, 30), width=4)
        g.text((360, y + 250), f"EPISODE {i}-{k + 1}", fill="black", font=font(36), anchor="mm")
    p = d / f"w{i:02d}.png"
    im.save(p)
    return str(p)


def settle(app, dlg):
    for _ in range(4000):
        app.processEvents()
        if not dlg._loader.isActive() and not dlg._resize_t.isActive():
            break
    app.processEvents()


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui.main_window import STYLE
    app.setStyleSheet(STYLE)
    from gui.exportdlg import ExportDialog

    manga = [manga_page(i, tmp) for i in range(1, 9)]
    pm = Project(pages=[Page(path=p, output_path=p if i != 6 else "") for i, p in enumerate(manga)],
                 series_title="Kisah Uji Coba")
    web = [webtoon_page(i, tmp) for i in range(1, 7)]
    pw = Project(pages=[Page(path=p, output_path=p) for p in web], series_title="Pahlawan Langit")

    shots = [
        ("1_pdf_manga", pm, 2, {"fmt": "pdf", "kind": "auto", "scope": "all"}),
        ("2_pdf_manhwa", pw, 0, {"fmt": "pdf", "kind": "manhwa", "scope": "all"}),
        ("3_cbz_mihon", pm, 0, {"fmt": "cbz", "kind": "manga", "scope": "range", "range": "2-5",
                                "mihon_pack": True, "img_fmt": "jpg"}),
        ("4_halaman_ini", pw, 3, {"fmt": "zip", "kind": "manhua", "scope": "cur"}),
    ]
    for name, proj, cur, opts in shots:
        dlg = ExportDialog(proj, cur, {"export_opts": opts}, None)
        if name == "3_cbz_mihon":
            dlg.m_ch.setText("12")
            dlg.m_title.setText("Awal Perjalanan")
            dlg.m_tl.setText("Reza")
            dlg.m_genre.setText("Action, Fantasy")
        dlg.resize(1180, 760)
        dlg.show()
        settle(app, dlg)
        dlg._relayout()
        settle(app, dlg)
        if name == "2_pdf_manhwa":
            dlg.strip.verticalScrollBar().setValue(1500)
            settle(app, dlg)
        dlg.grab().save(str(out / f"{name}.png"))
        print(name, "ok", dlg.summary.text(), "|", dlg.sel_info.text())
        dlg.close()

    from core import exporter
    r = exporter.export(pm, str(out / "tes.cbz"), fmt="cbz", kind="manga", indices=list(range(8)), meta={"chapter": "1"})
    print("export", r)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
