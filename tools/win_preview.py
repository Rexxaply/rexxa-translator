"""Windows asli: cek animasi buka/tutup kartu & ganti tab panel (dev)."""
import base64
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui import main_window as mw
    from gui.glass import install_popup_fx, install_smooth_scroll
    install_popup_fx(app)
    install_smooth_scroll(app)
    app.setStyleSheet(mw.STYLE)
    w = mw.MainWindow()
    w.resize(1000, 700)
    w.show()

    def pump(s):
        t = time.time()
        while time.time() - t < s:
            app.processEvents()
            time.sleep(0.002)

    def shot(name, widget):
        pm = widget.grab()
        pm.save(f"{name}.png")
        print("===B64===", name)
        print(base64.b64encode(Path(f"{name}.png").read_bytes()).decode())
        print("===END===")

    pump(0.6)
    import tempfile
    import cv2
    import numpy as np
    from core.models import Page, Project, TextBlock
    d = Path(tempfile.mkdtemp())
    img = np.full((1400, 900, 3), 235, np.uint8)
    cv2.ellipse(img, (450, 400), (230, 140), 0, 0, 360, (0, 0, 0), 4)
    cv2.imwrite(str(d / "a.png"), img)
    pg = Page(path=str(d / "a.png"), blocks=[TextBlock(x=230, y=270, w=440, h=260, source="HELLO",
                                                         translation="Halo", src_h=28)])
    f = str(d / "t.mtproj")
    Project(pages=[pg], source_lang="en", target_lang="id").save(f)
    w._load_project(f)
    pump(0.6)
    w.toggle_inspector(True)
    pump(0.8)
    w._select(w.page().blocks[0])
    pump(0.4)
    sec = w.sections[1]
    full = sec.body.height()
    print("tinggi awal Tipografi:", full, "visible", sec.body.isVisible())

    def sample(label, dur):
        t0 = time.perf_counter()
        rows = []
        while time.perf_counter() - t0 < dur:
            app.processEvents()
            fx = sec.body.graphicsEffect()
            rows.append((int((time.perf_counter() - t0) * 1000), sec.body.height(),
                         round(fx.opacity(), 2) if fx else None))
            time.sleep(0.02)
        print(label, rows)

    sec.btn.click()                        # tutup
    sample("TUTUP (ms, tinggi, opacity):", 0.32)
    print("setelah tutup: visible", sec.body.isVisible(), "efek", sec.body.graphicsEffect(),
          "maxH", sec.body.maximumHeight())
    shot("anim_1_tutup", w.insp_slide)
    sec.btn.click()                        # buka
    pump(0.09)
    shot("anim_2_tengah", w.insp_slide)
    sample("BUKA (ms, tinggi, opacity):", 0.3)
    print("setelah buka: tinggi", sec.body.height(), "dari", full, "visible", sec.body.isVisible(),
          "efek", sec.body.graphicsEffect(), "maxH", sec.body.maximumHeight())

    # klik cepat bolak-balik (tidak boleh macet setengah)
    for _ in range(5):
        sec.btn.click()
        pump(0.04)
    pump(0.4)
    print("setelah 5x klik cepat: checked", sec.btn.isChecked(), "visible", sec.body.isVisible(),
          "tinggi", sec.body.height(), "efek", sec.body.graphicsEffect())

    # ganti tab
    tw = w.tabs
    tw.setCurrentIndex(1)
    page = tw.widget(1)
    t0 = time.perf_counter()
    rows = []
    while time.perf_counter() - t0 < 0.26:
        app.processEvents()
        fx = page.graphicsEffect()
        rows.append((int((time.perf_counter() - t0) * 1000), page.y(), round(fx.opacity(), 2) if fx else None))
        time.sleep(0.02)
    print("TAB BALON (ms, y, opacity):", rows)
    pump(0.1)
    shot("anim_3_tab_balon", w.insp_slide)
    tw.setCurrentIndex(0)
    pump(0.04)
    shot("anim_4_tab_tengah", w.insp_slide)
    pump(0.4)
    print("tab properti y", tw.widget(0).y(), "efek", tw.widget(0).graphicsEffect())
    shot("anim_5_akhir", w)


if __name__ == "__main__":
    main()
