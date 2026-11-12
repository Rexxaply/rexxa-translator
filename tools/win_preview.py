"""Windows asli: ukur jeda dari ketikan ke hasil tampil (dev)."""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageGrab  # noqa: E402
from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def make_project(d: Path):
    from core.models import Page, Project, TextBlock
    W, H = 900, 2600
    src = np.full((H, W, 3), 255, np.uint8)
    blocks = []
    for i in range(6):
        cy = 220 + i * 410
        cv2.ellipse(src, (450, cy), (230, 150), 0, 0, 360, (0, 0, 0), 4)
        blocks.append(TextBlock(x=270, y=cy - 110, w=360, h=220, source="TEXT",
                                translation="Kamu beneran nggak apa-apa?", src_h=28,
                                text_rect=[300, cy - 70, 300, 140]))
    clean = src.copy()
    for i in range(6):
        cy = 220 + i * 410
        cv2.putText(src, "WHY ARE YOU", (330, cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 3)
    cv2.imwrite(str(d / "p1.png"), src)
    cv2.imwrite(str(d / "p1_clean.png"), clean)
    proj = Project(pages=[Page(path=str(d / "p1.png"), blocks=blocks, status="selesai",
                               cleaned_path=str(d / "p1_clean.png"))], source_lang="en", target_lang="id")
    f = str(d / "tes.mtproj")
    proj.save(f)
    return f


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp())
    f = make_project(d)
    from gui import main_window as mw
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(mw.STYLE)
    w = mw.MainWindow()
    w.resize(1000, 740)
    w.move(10, 10)
    w.show()

    def pump(sec):
        t = time.time()
        while time.time() - t < sec:
            app.processEvents()
            time.sleep(0.002)
    pump(1.5)
    w._load_project(f)
    pump(1.0)
    w.render_current()
    t = time.time()
    while w.thread and time.time() - t < 30:
        pump(0.05)
    pump(1.0)
    p = w.page()
    w._select(p.blocks[1])
    pump(0.5)
    fc = w.p_font
    print("jumlah font:", fc.count(), [fc.itemText(i) for i in range(fc.count())], flush=True)
    le = fc.lineEdit()
    fc.setCurrentIndex(fc.findText("Arial"))
    pump(0.4)
    shots = []

    def grab():
        g = fc.mapToGlobal(fc.rect().topLeft())
        x0, y0 = g.x() - 200, g.y() - 60
        return ImageGrab.grab(bbox=(x0, y0, x0 + 480, y0 + 420), all_screens=True)
    w.activateWindow()
    QTest.mouseClick(le, Qt.LeftButton, Qt.NoModifier, le.rect().center())
    pump(0.5)
    pop = fc._comp.popup()
    print("klik -> daftar tampil", pop.isVisible(), "| jumlah", fc._proxy.rowCount(),
          "| terpilih", pop.currentIndex().data(), "| teks", repr(le.text()), "| terseleksi", le.hasSelectedText(), flush=True)
    shots.append(grab())
    QTest.keyClicks(pop if pop.isVisible() else le, "co")
    pump(0.4)
    print("ketik 'co' -> teks", repr(le.text()), "| hasil",
          [fc._proxy.index(i, 0).data() for i in range(fc._proxy.rowCount())], flush=True)
    shots.append(grab())
    QTest.keyClick(pop if pop.isVisible() else le, Qt.Key_Return)
    pump(0.5)
    print("Enter -> font balon:", p.blocks[1].font, "| teks", repr(le.text()), flush=True)
    shots.append(grab())
    sw, sh = shots[0].width, shots[0].height
    sheet = Image.new("RGB", (sw * 3, sh), "black")
    for i, im in enumerate(shots[:3]):
        sheet.paste(im, (i * sw, 0))
    sheet.save(out / "cari_font.png")
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "shots")
