"""Uji dropdown baru + Pengaturan tanpa kedipan (dev)."""
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
    from gui.glass import install_popup_fx
    install_popup_fx(app)
    from core.paths import code_dir
    chev = (code_dir() / "assets" / "chevron_down.svg").as_posix()
    app.setStyleSheet(mw.STYLE + "QComboBox::down-arrow { image: url(%s); width: 10px; height: 10px; }" % chev)
    w = mw.MainWindow()
    w.resize(1280, 800)
    w.move(0, 0)
    w.show()
    pump(app, 0.8)
    from core import pipeline
    s = w.settings
    s["engine_presets"].append(dict(pipeline.engine_values(s), name="Preset 2"))
    s["engine_presets"].append(dict(pipeline.engine_values(s), name="Gemini cadangan"))
    s["_settings_tab"] = 1
    from gui.dialogs import SettingsDialog
    dlg = SettingsDialog(s, w, project=w.project)
    pos0 = dlg.pos()
    dlg.show()                                   # frame pertama setelah tampil
    first = pil(dlg.grab().toImage())
    alpha = sum(first.getchannel("A").getdata()) / (first.width * first.height * 255)
    print("frame pertama: isi tersembunyi =", not dlg.sheet.isVisible(), "| kepekatan rata-rata =", round(alpha, 3),
          "| posisi sudah final =", dlg.pos() != pos0, flush=True)
    p_show = dlg.pos()
    pump(app, 0.8)
    print("posisi tidak berubah selama animasi =", dlg.pos() == p_show, "| isi tampil setelah animasi =",
          dlg.sheet.isVisible(), flush=True)
    dlg.ep.showPopup()
    pump(app, 0.5)
    cont = dlg.ep.view().window()
    print("dropdown preset: x popup =", cont.mapToGlobal(QPoint(0, 0)).x(), "| x kotak =", dlg.ep.mapToGlobal(QPoint(0, 0)).x(),
          flush=True)
    from PySide6.QtCore import Qt
    print("popup transparan bersudut =", cont.testAttribute(Qt.WA_TranslucentBackground), flush=True)
    compose(w, dlg, cont).save(out / "1_dropdown_preset.png")
    dlg.ep.hidePopup()
    dlg.nav.setCurrentRow(0)
    pump(app, 0.3)
    dlg.clean.showPopup()
    pump(app, 0.5)
    compose(w, dlg, dlg.clean.view().window()).save(out / "2_dropdown_metode.png")
    dlg.clean.hidePopup()
    dlg._closing = None
    dlg.done(0)
    pump(app, 0.5)
    # dropdown & menu di jendela utama
    w.tgt.showPopup()
    pump(app, 0.5)
    c = w.tgt.view().window()
    print("dropdown bahasa: x popup =", c.mapToGlobal(QPoint(0, 0)).x(), "| x kotak =", w.tgt.mapToGlobal(QPoint(0, 0)).x(),
          "| y popup =", c.mapToGlobal(QPoint(0, 0)).y(), "| bawah kotak =", w.tgt.mapToGlobal(QPoint(0, w.tgt.height())).y(),
          flush=True)
    compose(w, c).crop((380, 0, 1280, 520)).save(out / "3_dropdown_bahasa.png")
    w.tgt.hidePopup()
    w._fill_engine_menu()
    m = w.b_go.menu()
    m.popup(w.b_go.mapToGlobal(QPoint(0, w.b_go.height())))
    pump(app, 0.5)
    compose(w, m).crop((380, 0, 1280, 560)).save(out / "4_menu_terjemahkan.png")
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
