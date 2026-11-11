"""Uji dialog Pengaturan Liquid Glass + animasi pop-up + preset engine (dev)."""
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
from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolTip  # noqa: E402


def pump(app, sec):
    t = time.time()
    while time.time() - t < sec:
        app.processEvents()
        time.sleep(0.004)


def pil(qimg):
    qimg = qimg.convertToFormat(qimg.Format.Format_RGBA8888)
    return Image.frombuffer("RGBA", (qimg.width(), qimg.height()), bytes(qimg.constBits()), "raw", "RGBA",
                            qimg.bytesPerLine(), 1).copy()


def compose(main, *wins):
    base = pil(main.grab().toImage()).convert("RGBA")
    o = main.mapToGlobal(QPoint(0, 0))
    for w in wins:
        if w is None or not w.isVisible():
            continue
        im = pil(w.grab().toImage())
        p = w.mapToGlobal(QPoint(0, 0)) - o
        base.alpha_composite(im, (max(0, p.x()), max(0, p.y())))
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
    for n in range(1, 4):
        im = Image.new("RGB", (600, 850), "white")
        ImageDraw.Draw(im).ellipse((150, 200, 450, 420), outline="black", width=4)
        im.save(d / f"{n:03d}.png")
    w._load_paths([str(d)])
    pump(app, 1.2)
    from core import pipeline
    s = w.settings
    s.update(translate_engine="llm", llm_preset="Kustom", llm_base_url="https://router.classai.id/v1",
             llm_model="claude-sonnet-5", llm_api_key="sk-test", llm_temperature=0.3)
    pipeline.store_engine_preset(s, "Default")
    s2 = dict(s, llm_preset="Gemini", llm_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
              llm_model="gemini-2.5-flash")
    s["engine_presets"].append(dict(pipeline.engine_values(s2), name="Gemini cadangan"))
    s["engine_presets"].append(dict(pipeline.engine_values(dict(s, translate_engine="google")), name="Google darurat"))

    from gui.dialogs import NameDialog, SettingsDialog
    s["_settings_tab"] = 1
    dlg = SettingsDialog(s, w, project=w.project)
    frames = []
    t0 = time.time()
    dlg.show()
    nxt = 0
    while time.time() - t0 < 0.75:
        app.processEvents()
        if time.time() - t0 >= nxt:
            frames.append(compose(w, dlg).resize((960, 600), Image.LANCZOS))
            nxt += 0.025
    print("frame pop:", len(frames), flush=True)
    frames[0].save(out / "pop.gif", save_all=True, append_images=frames[1:] + [frames[-1]] * 20, duration=25, loop=0)
    pump(app, 0.3)
    compose(w, dlg).save(out / "1_terjemahan.png")
    # tooltip catatan
    lab = dlg.model
    QToolTip.showText(lab.mapToGlobal(QPoint(40, 30)), lab.toolTip(), lab)
    pump(app, 0.3)
    tips = [x for x in QApplication.topLevelWidgets() if x.metaObject().className() == "QTipLabel" and x.isVisible()]
    compose(w, dlg, *tips).save(out / "2_tooltip.png")
    QToolTip.hideText()
    for i, name in ((0, "3_proses"), (6, "4_data")):
        dlg.nav.setCurrentRow(i)
        pump(app, 0.3)
        compose(w, dlg).save(out / f"{name}.png")
    dlg.nav.setCurrentRow(1)
    pump(app, 0.2)
    nd = NameDialog(dlg, "Ganti nama preset", "Default", ["Gemini cadangan", "Google darurat"])
    nd.edit.setText("Claude via ClassAI")
    nd.show()
    pump(app, 0.7)
    compose(w, dlg, nd).save(out / "5_ganti_nama.png")
    nd.accept()
    pump(app, 0.4)
    # pindah preset di dialog -> kolom berubah
    dlg.ep.setCurrentText("Gemini cadangan")
    pump(app, 0.2)
    print("preset Gemini -> model:", dlg.model.text(), flush=True)
    dlg.ep.setCurrentText("Google darurat")
    pump(app, 0.2)
    print("preset Google -> kolom LLM terlihat:", dlg.model.isVisible(), flush=True)
    dlg.ep.setCurrentText("Default")
    pump(app, 0.2)
    # tutup dengan animasi
    t0 = time.time()
    dlg.reject()
    while dlg.isVisible() and time.time() - t0 < 2:
        app.processEvents()
    print("tutup:", round(time.time() - t0, 2), "dtk", flush=True)
    res = dlg.result_settings()
    print("aktif:", res["engine_preset"], "| preset:", [p["name"] for p in res["engine_presets"]], flush=True)
    # menu cepat di tombol Terjemahkan
    w._fill_engine_menu()
    m = w.m_engine
    m.popup(w.b_go.mapToGlobal(QPoint(0, w.b_go.height())))
    pump(app, 0.4)
    compose(w, m).crop((0, 0, 1280, 420)).save(out / "6_menu_preset.png")
    m.hide()
    w.use_engine_preset("Gemini cadangan")
    print("pakai preset dari menu ->", w.settings["engine_preset"], w.settings["llm_model"], flush=True)
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
