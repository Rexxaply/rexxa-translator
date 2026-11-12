"""Windows asli: uji kotak teks yang tingginya mengikuti isi (dev)."""
import base64
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, QRect, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui import main_window as mw
    from gui.glass import install_popup_fx, install_smooth_scroll
    from core.models import Page, Project, TextBlock
    install_popup_fx(app)
    install_smooth_scroll(app)
    app.setStyleSheet(mw.STYLE)
    w = mw.MainWindow()
    w.resize(1020, 720)
    w.show()

    def pump(t):
        e = time.time() + t
        while time.time() < e:
            app.processEvents()
            time.sleep(0.002)

    shots = []

    def grab(label):
        ins = w.insp_slide
        r = QRect(ins.mapTo(w, ins.rect().topLeft()), ins.size())
        r.setHeight(300)
        shots.append((label, w.grab(r)))

    d = Path(tempfile.mkdtemp())
    img = np.full((1300, 900, 3), 235, np.uint8)
    cv2.imwrite(str(d / "a.png"), img)
    long_src = ("AT 20 YEARS OLD; I WANT TO DRIVE AROUND IN A FOREIGN CAR; AT 25 I WANT A HOUSE BY THE SEA "
                "AND AT 30 I WANT TO RETIRE AND TRAVEL THE WORLD WITH MY FRIENDS EVERY SINGLE YEAR")
    blocks = [TextBlock(x=100, y=100, w=300, h=150, source="HI!", translation="Hai!"),
              TextBlock(x=100, y=400, w=300, h=150, source="AT 20 YEARS OLD; I WANT TO DRIVE AROUND IN A FOREIGN CAR",
                        translation="Di Umur 20 tahun, aku pengen nyetir mobil Impor"),
              TextBlock(x=100, y=700, w=300, h=150, source=long_src,
                        translation="Umur 20 aku mau nyetir mobil impor, umur 25 punya rumah di tepi laut, "
                                    "umur 30 pensiun dan keliling dunia bareng teman-teman setiap tahun tanpa henti")]
    f = str(d / "t.mtproj")
    Project(pages=[Page(path=str(d / "a.png"), blocks=blocks)], source_lang="en", target_lang="id").save(f)
    w._load_project(f)
    pump(1.0)
    if not w.insp_slide.open:
        w.toggle_inspector(True)
        pump(1.0)
    ls = w.e_src.fontMetrics().lineSpacing()
    print("tinggi 1 baris font:", ls, flush=True)
    for i, label in enumerate(("1 baris", "2 baris", "6 baris")):
        w._select(w.page().blocks[i])
        pump(0.5)
        print(f"{label}: asli h={w.e_src.height()} gulir={w.e_src.verticalScrollBar().isVisible()} | "
              f"terjemahan h={w.e_tr.height()} gulir={w.e_tr.verticalScrollBar().isVisible()}", flush=True)
        grab(label)
    # mengetik: tumbuh beranimasi
    w._select(w.page().blocks[0])
    pump(0.4)
    w.e_tr.setFocus()
    from PySide6.QtGui import QTextCursor
    w.e_tr.moveCursor(QTextCursor.End)
    hs = [w.e_tr.height()]
    QTest.keyClicks(w.e_tr, " ini kalimat tambahan yang panjang supaya kotaknya ikut bertambah tinggi")
    t0 = time.time()
    while time.time() - t0 < 0.25:
        app.processEvents()
        hs.append(w.e_tr.height())
        time.sleep(0.015)
    print("mengetik -> tinggi berubah:", sorted(set(hs)), flush=True)
    # gulir halus di kotak 6 baris
    w._select(w.page().blocks[2])
    pump(0.5)
    e = w.e_src
    sb = e.verticalScrollBar()
    vp = e.viewport()
    pos = QPointF(vp.width() / 2, vp.height() / 2)
    vals = [sb.value()]
    ev = QWheelEvent(pos, vp.mapToGlobal(pos), QPoint(0, 0), QPoint(0, -120), Qt.NoButton, Qt.NoModifier,
                     Qt.ScrollUpdate, False)
    app.sendEvent(vp, ev)
    t0 = time.time()
    while time.time() - t0 < 0.4:
        app.processEvents()
        vals.append(sb.value())
        time.sleep(0.015)
    print("gulir 1 notch: nilai", vals[:1], "->", sorted(set(vals)), "maks", sb.maximum(), flush=True)
    grab("6 baris (digulir)")
    from PySide6.QtGui import QColor, QPainter, QPixmap
    W = sum(p.width() for _, p in shots) + 12 * (len(shots) + 1)
    H = max(p.height() for _, p in shots) + 30
    out = QPixmap(W, H)
    out.fill(QColor(16, 18, 26))
    pt = QPainter(out)
    pt.setPen(QColor(220, 224, 240))
    x = 12
    for label, pm in shots:
        pt.drawText(x + 4, 18, label)
        pt.drawPixmap(x, 26, pm)
        x += pm.width() + 12
    pt.end()
    out.save("auto.png")
    print("===B64=== auto")
    print(base64.b64encode(Path("auto.png").read_bytes()).decode())
    print("===END===", flush=True)


if __name__ == "__main__":
    main()
