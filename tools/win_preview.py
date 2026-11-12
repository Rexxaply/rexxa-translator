"""Windows asli: uji gulir halus di semua daftar (dev)."""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def main():
    from gui import main_window as mw
    from core.models import Page, Project, TextBlock
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui.glass import install_popup_fx, install_smooth_scroll
    install_popup_fx(app)
    install_smooth_scroll(app)
    app.setStyleSheet(mw.STYLE)
    d = Path(tempfile.mkdtemp())
    pages = []
    for i in range(25):
        img = np.full((1200, 800, 3), 240, np.uint8)
        cv2.putText(img, str(i + 1), (300, 600), cv2.FONT_HERSHEY_SIMPLEX, 6, (0, 0, 0), 12)
        cv2.imwrite(str(d / f"{i:02d}.png"), img)
        pages.append(Page(path=str(d / f"{i:02d}.png"),
                          blocks=[TextBlock(x=100, y=100 + k * 30, w=200, h=25, source=f"line {k}",
                                            translation=f"baris {k}") for k in range(30)] if i == 0 else []))
    f = str(d / "t.mtproj")
    Project(pages=pages).save(f)
    w = mw.MainWindow()
    w.resize(1000, 700)
    w.show()

    def pump(s):
        t = time.time()
        while time.time() - t < s:
            app.processEvents()
            time.sleep(0.002)
    pump(1)
    w._load_project(f)
    pump(1.5)
    w._select(w.page().blocks[0])
    pump(0.5)

    def test(name, area, pix=0):
        vp = area.viewport()
        bar_v, bar_h = area.verticalScrollBar(), area.horizontalScrollBar()
        v0, h0 = bar_v.value(), bar_h.value()
        c = QPointF(vp.width() / 2, vp.height() / 2)
        vals = []
        t0 = time.time()
        for _ in range(2):
            ev = QWheelEvent(c, QPointF(vp.mapToGlobal(c.toPoint())), QPoint(0, -pix), QPoint(0, 0 if pix else -120),
                             Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
            QApplication.sendEvent(vp, ev)
            t1 = time.time()
            while time.time() - t1 < 0.32:
                app.processEvents()
                vals.append((round((time.time() - t0) * 1000), bar_v.value(), bar_h.value()))
        ch = [v for i, v in enumerate(vals) if i == 0 or v[1:] != vals[i - 1][1:]]
        print(f"{name}: awal v{v0}/h{h0} -> akhir v{bar_v.value()}/h{bar_h.value()} | langkah frame: {len(ch)} | "
              f"contoh {ch[:6]}", flush=True)

    props = w.tabs.widget(0)
    test("panel properti", props)
    test("panel properti (touchpad 7px)", props, pix=7)
    w.tabs.setCurrentIndex(1)
    pump(0.3)
    test("tabel balon", w.table)
    w.tabs.setCurrentIndex(2)
    pump(0.3)
    for i in range(80):
        w.log(f"log {i}")
    pump(0.3)
    w.logbox.verticalScrollBar().setValue(0)
    test("log", w.logbox)
    test("strip halaman", w.pages)
    z0 = w.cv_src.zoom()
    vp = w.cv_src.viewport()
    c = QPointF(vp.width() / 2, vp.height() / 2)
    QApplication.sendEvent(vp, QWheelEvent(c, QPointF(vp.mapToGlobal(c.toPoint())), QPoint(), QPoint(0, 120),
                                           Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
    pump(0.3)
    print("kanvas: roda tetap zoom", round(z0, 3), "->", round(w.cv_src.zoom(), 3), flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
