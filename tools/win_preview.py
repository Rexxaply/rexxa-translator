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
    w.resize(1400, 900)
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
    shows = []
    orig = w.cv_out.show_live

    def spy(img, rect=None):
        t0 = time.perf_counter()
        orig(img, rect)
        shows.append((time.perf_counter(), (time.perf_counter() - t0) * 1000))
    w.cv_out.show_live = spy
    w.e_tr.setFocus()
    w.e_tr.selectAll()
    QTest.keyClick(w.e_tr, Qt.Key_Delete)
    pump(0.4)
    text = "TOLONG JANGAN MENDEKAT"
    keys = []
    shots = []
    g = w.cv_out
    tl = g.mapToGlobal(g.rect().topLeft())
    box = (tl.x(), tl.y(), tl.x() + g.width(), tl.y() + g.height())
    for ch in text:
        keys.append(time.perf_counter())
        QTest.keyClicks(w.e_tr, ch)
        pump(0.09)
        shots.append(ImageGrab.grab(bbox=box, all_screens=True))
    pump(1.2)
    # ---- geser kotak balon 2 ke bawah-kanan (seperti menyeret dengan mouse), lalu lepas
    shows_before = len(shows)
    w._on_edit_started(p.blocks[1])
    pump(0.2)
    item = next(bx for bx in w.cv_out.boxes if bx.block is p.blocks[1])
    start = item.pos()
    drag = []
    dshots = []
    for k in range(1, 13):
        drag.append(time.perf_counter())
        item = next(bx for bx in w.cv_out.boxes if bx.block is p.blocks[1])
        item.setPos(start.x() + k * 12, start.y() + k * 22)
        item.sync()
        w.cv_out.block_moving.emit(p.blocks[1])
        pump(0.07)
        if k in (3, 6, 9, 12):
            dshots.append(ImageGrab.grab(bbox=box, all_screens=True))
    w.cv_out.block_geometry_changed.emit(p.blocks[1])
    t = time.time()
    pump(0.4)
    while w.thread and time.time() - t < 30:
        pump(0.05)
    pump(0.8)
    dshots.append(ImageGrab.grab(bbox=box, all_screens=True))
    dl = []
    for k in drag:
        nxt = [x for x in shows[shows_before:] if x[0] >= k]
        dl.append(round((nxt[0][0] - k) * 1000) if nxt else None)
    print("jeda geser -> tampil (ms):", dl, flush=True)
    sw2, sh2 = dshots[0].width // 2, dshots[0].height // 2
    sheet2 = Image.new("RGB", (sw2 * len(dshots), sh2), "black")
    for i, im in enumerate(dshots):
        sheet2.paste(im.resize((sw2, sh2)), (i * sw2, 0))
    sheet2.save(out / "geser.png")
    lat = []
    for k in keys:
        nxt = [s for s in shows if s[0] >= k]
        lat.append(round((nxt[0][0] - k) * 1000) if nxt else None)
    print("jeda ketikan -> tampil (ms):", lat, flush=True)
    print("waktu gambar ke kanvas (ms):", [round(s[1], 1) for s in shows], flush=True)
    print("output:", p.output_path, Path(p.output_path).exists() if p.output_path else None, flush=True)
    sel = [shots[i] for i in (0, 2, 5, 8, 12, 16, 19, len(shots) - 1)]
    sw, sh = sel[0].width // 2, sel[0].height // 2
    sheet = Image.new("RGB", (sw * 4, sh * 2), "black")
    for i, im in enumerate(sel):
        sheet.paste(im.resize((sw, sh)), ((i % 4) * sw, (i // 4) * sh))
    sheet.save(out / "ketik.png")
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "shots")
