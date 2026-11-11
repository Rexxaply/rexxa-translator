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
    os.environ["XDG_CONFIG_HOME"] = str(tmp / "cfg")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui.main_window import STYLE
    app.setStyleSheet(STYLE)
    from core.models import TextBlock
    from gui.exportdlg import ExportDialog
    from gui.skillsdlg import CreditsDialog, ProofreadDialog, StoryDialog

    manga = [manga_page(i, tmp) for i in range(1, 6)]
    pm = Project(pages=[Page(path=p, output_path=p) for p in manga], series_title="Kisah Uji Coba",
                 source_lang="ja", target_lang="id")
    pm.export_meta = {"series": "Kisah Uji Coba", "chapter": "12", "chapter_title": "Awal Perjalanan"}
    pm.story = {"characters": [
        {"name": "Aiko", "source": "愛子", "gender": "perempuan", "call": "aku/kamu; panggil Ren 'kak'",
         "speech": "ceria, cepat", "notes": "adik Ren"},
        {"name": "Ren", "source": "蓮", "gender": "laki-laki", "call": "gue/lo", "speech": "dingin, singkat",
         "notes": "kakak Aiko, kapten"},
        {"name": "Duke Elric", "source": "エルリック公爵", "gender": "laki-laki", "call": "saya/Anda",
         "speech": "formal", "notes": "tunangan Aiko"}], "notes": "Latar: akademi sihir. 'Mana' tidak diterjemahkan."}
    rows = [("愛子、待って！", "Aiko, tunggu!"), ("どこに行くの？", "Mau pergi kemana"),
            ("蓮先輩は来ない", "Ren  senpai tidak tidak datang."), ("ありがとう", ""),
            ("エルリック公爵が呼んでいる", "Sang adipati memanggilmu.")]
    pm.pages[0].blocks = [TextBlock(x=100 + 60 * k, y=100 + 200 * k, w=260, h=150, source=a, translation=b,
                                    src_h=30, fit_size=(14 if k == 4 else 28)) for k, (a, b) in enumerate(rows)]
    st = {"credits": {"team": "Rexxa Scans", "roles": "Penerjemah: Reza\nEditor: Budi\nTypesetter: Reza",
                      "wm_text": "Rexxa Scans"}, "export_opts": {"fmt": "cbz", "kind": "manga",
                                                                 "credit_page": True, "watermark": True}}

    def snap(name, dlg, w=1100, h=700):
        dlg.resize(w, h)
        dlg.show()
        for _ in range(3000):
            app.processEvents()
            ld = getattr(dlg, "_loader", None)
            if not (ld and ld.isActive()):
                break
        for _ in range(50):
            app.processEvents()
        if hasattr(dlg, "_preview"):
            dlg._preview()
            app.processEvents()
        dlg.grab().save(str(out / f"{name}.png"))
        print(name, "ok", flush=True)
        dlg.close()
        dlg.deleteLater()
        for _ in range(20):
            app.processEvents()
        print(name, "deleted", flush=True)

    snap("1_memori", StoryDialog(pm, dict(st)), 1080, 620)
    snap("2_proofread", ProofreadDialog(pm, dict(st), 0), 1080, 560)
    snap("3_kredit", CreditsDialog(dict(st), pm.export_meta, manga[0]), 1000, 680)
    d = ExportDialog(pm, 0, dict(st))
    snap("4_export_kredit", d, 1180, 800)
    st2 = dict(st, export_opts={"fmt": "psd"})
    snap("5_export_psd", ExportDialog(pm, 0, st2), 1180, 760)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
