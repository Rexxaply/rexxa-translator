"""Windows asli: foto layar dropdown & menu untuk memeriksa pojok hitam (dev)."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image, ImageGrab  # noqa: E402
from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox, QMenu, QVBoxLayout, QWidget  # noqa: E402


def pump(app, sec):
    t = time.time()
    while time.time() - t < sec:
        app.processEvents()
        time.sleep(0.01)


def snap(w, name, out, pad=30):
    g = w.frameGeometry()
    box = (g.left() - pad, g.top() - pad, g.right() + pad, g.bottom() + pad)
    im = ImageGrab.grab(bbox=box, all_screens=True)
    im = im.resize((im.width * 3, im.height * 3), Image.NEAREST)
    im.save(out / name)


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    import platform
    print("Windows:", platform.platform(), flush=True)
    from gui import main_window as mw
    from gui.glass import install_popup_fx
    install_popup_fx(app)
    app.setStyleSheet(mw.STYLE)
    host = QWidget()
    host.setObjectName("host")
    host.setStyleSheet("QWidget#host { background: #f2efe8; }")
    host.resize(520, 380)
    host.move(100, 100)
    lay = QVBoxLayout(host)
    cb = QComboBox()
    cb.addItems(["Otomatis", "manga-ocr (Jepang)", "EasyOCR"])
    lay.addWidget(cb)
    lay.addStretch()
    host.show()
    host.raise_()
    host.activateWindow()
    pump(app, 1.0)
    cb.showPopup()
    pump(app, 1.0)
    cont = cb.view().window()
    print("flags:", int(cont.windowFlags()), "translucent:", cont.testAttribute(Qt.WA_TranslucentBackground), flush=True)
    snap(cont, "1_dropdown.png", out)
    cb.hidePopup()
    pump(app, 0.3)
    m = QMenu(host)
    for t in ("Terjemahkan SEMUA halaman", "Hanya OCR", "Render ulang"):
        m.addAction(t)
    m.popup(host.mapToGlobal(QPoint(40, 80)))
    pump(app, 1.0)
    snap(m, "2_menu.png", out)
    m.hide()
    host.hide()
    # Pengaturan di atas jendela utama: foto layar berurutan sejak klik
    w = mw.MainWindow()
    w.resize(1100, 720)
    w.move(40, 20)
    w.show()
    w.raise_()
    w.activateWindow()
    pump(app, 1.5)
    from gui.dialogs import SettingsDialog
    from PySide6.QtCore import QEvent, QObject
    import threading

    def run(label, grab):
        dlg = SettingsDialog(w.settings, w, project=w.project)
        T0 = [time.perf_counter()]
        log = []

        class Spy(QObject):
            def eventFilter(self, o, e):
                if o is dlg and e.type() == QEvent.Paint:
                    a = dlg._anim
                    log.append((round((time.perf_counter() - T0[0]) * 1000),
                                None if a is None else round(a["u"], 2), round(dlg.windowOpacity(), 1)))
                return False
        spy = Spy()
        app.installEventFilter(spy)
        g = w.frameGeometry()
        box = (g.left(), g.top(), g.right(), g.bottom())
        shots = []
        stop = [False]

        def grabber():
            while not stop[0]:
                shots.append((round((time.perf_counter() - T0[0]) * 1000), ImageGrab.grab(bbox=box, all_screens=True)))
        T0[0] = time.perf_counter()
        th = threading.Thread(target=grabber, daemon=True)
        if grab:
            th.start()
        dlg.show()
        print(label, "show() selesai", round((time.perf_counter() - T0[0]) * 1000), "ms", flush=True)
        while time.perf_counter() - T0[0] < (1.6 if grab else 0.9):
            app.processEvents()
            time.sleep(0.001)
        stop[0] = True
        if grab:
            th.join()
        app.removeEventFilter(spy)
        print(label, "paint (ms, u, opacity):", log[:60], flush=True)
        gaps = [log[i + 1][0] - log[i][0] for i in range(len(log) - 1)]
        print(label, "jeda antar frame terbesar:", max(gaps) if gaps else None, flush=True)
        return dlg, shots

    d1, _ = run("A", False)
    d1.done(0)
    pump(app, 0.6)
    dlg, shots = run("B", True)
    print("foto:", [s_[0] for s_ in shots][:40], flush=True)
    t_show = next((t for t, u, op in [] ), None)
    shots = [x for x in shots if x[0] >= 700] or shots
    idx = sorted({round(i * (len(shots) - 1) / 7) for i in range(8)})
    sw, sh = 550, 360
    sheet = Image.new("RGB", (sw * 4, sh * 2), "black")
    for i, k in enumerate(idx[:8]):
        sheet.paste(shots[k][1].resize((sw, sh)), ((i % 4) * sw, (i // 4) * sh))
    sheet.save(out / "3_pengaturan_buka.png")
    dlg.ocr.showPopup()
    pump(app, 0.8)
    snap(dlg.ocr.view().window(), "4_dropdown_di_pengaturan.png", out)
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "shots")
