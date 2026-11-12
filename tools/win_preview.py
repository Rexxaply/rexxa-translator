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
    from gui.glass import install_popup_fx
    install_popup_fx(app)
    app.setStyleSheet(mw.STYLE)
    scr = app.primaryScreen().availableGeometry()
    print("layar:", scr.width(), scr.height(), flush=True)
    w = mw.MainWindow()
    w.resize(1440, 900)
    w.move(0, 0)
    w.show()

    def pump(sec):
        t = time.time()
        while time.time() - t < sec:
            app.processEvents()
            time.sleep(0.002)

    def shot(name, popup=None):
        img = w.grab().toImage()          # render jendela 1440x900 apa adanya (tidak terpotong layar runner)
        if popup is not None:
            from PySide6.QtGui import QPainter
            pt = QPainter(img)
            pos = w.mapFromGlobal(popup.mapToGlobal(popup.rect().topLeft()))
            pt.drawImage(pos, popup.grab().toImage())
            pt.end()
        img.save(str(out / name))
    pump(1.5)
    shot("0_awal.png")
    w._load_project(f)
    pump(1.0)
    w.render_current()
    t = time.time()
    while w.thread and time.time() - t < 30:
        pump(0.05)
    pump(1.0)
    p = w.page()
    w._select(p.blocks[1])
    pump(0.8)
    w.p_stroke.setValue(3, emit=True)
    pump(0.3)
    shot("1_editor.png")
    w.p_stroke.setFocus()
    w.p_stroke.selectAll()
    QTest.keyClicks(w.p_stroke, "0")
    pump(0.4)
    print("ketik 0 di tebal garis ->", repr(w.p_stroke.text()), "| nilai", w.p_stroke.value(),
          "| stroke balon", p.blocks[1].stroke_width, flush=True)
    # klik kanan alat balon -> daftar grup
    def grab_menu():
        pump(0.5)
        m = QApplication.activePopupWidget()
        shot("2_grup_alat.png", popup=m)
        print("menu grup:", m is not None and [a.text() for a in m.actions()], flush=True)
        if m:
            m.close()
    QTimer.singleShot(0, grab_menu)
    w.g_box.show_menu()
    pump(0.3)

    def grab_go():
        pump(0.5)
        m = QApplication.activePopupWidget()
        shot("2b_terjemahkan.png", popup=m)
        if m:
            m.close()
    QTimer.singleShot(0, grab_go)
    w.b_go.showMenu()
    pump(0.4)
    # oval: gambar balon oval baru + sembunyikan panel dengan animasi
    w.g_box.set_current("box_oval")
    w.g_box.setChecked(True)
    w._pick_box_tool("box_oval")
    from PySide6.QtCore import QRectF
    w.cv_src.box_drawn.emit(QRectF(330, 1900, 260, 170))
    pump(1.0)
    print("balon oval:", p.blocks[-1].kind, p.blocks[-1].shape, len(p.blocks[-1].mask_poly), flush=True)
    frames = []
    w.toggle_inspector(False)
    t0 = time.time()
    while time.time() - t0 < 0.6:
        app.processEvents()
        frames.append((round((time.time() - t0) * 1000), w.insp_slide.width(), w.insp_slide.minimumWidth()))
    print("lebar panel selama animasi:", [f for i, f in enumerate(frames) if i == 0 or f[1] != frames[i - 1][1]][:30], flush=True)
    pump(0.8)
    w.b_layers.setChecked(False)
    pump(0.5)
    shot("3_panel_tutup.png")
    w.toggle_inspector(True)
    w.b_layers.setChecked(True)
    w.set_tool("patch")
    w._pick_group_tool("shape_oval")
    w.set_tool("patch")
    pump(1.0)
    print("ikon grup:", w.tool_groups["heal"].current, w.tool_groups["shape"].current, w.g_box.current, flush=True)
    shot("4_ikon_grup.png")
    # ---- tombol P = Seleksi kotak (seret), Shift = persegi
    from PySide6.QtCore import QPoint, QPointF as _PF, QEvent as _E
    from PySide6.QtGui import QMouseEvent
    w.set_tool("select")
    w._pick_group_tool("shape_oval")          # mulai dari oval supaya terlihat P mengembalikan ke kotak
    pump(0.2)
    cv = w.cv_src
    cv.setFocus()
    w.activateWindow()
    pump(0.3)
    w.set_tool("heal")
    pump(0.2)
    QTest.keyClick(cv, Qt.Key_K)
    pump(0.4)
    print("tekan K -> alat:", w.tool, "| grup Perbaikan:", w.tool_groups["heal"].current, "| isi grup:",
          [v[2] for v in w.tool_groups["heal"].variants], flush=True)
    w.set_tool("heal")
    QTest.keyClick(cv, Qt.Key_P)
    pump(0.4)
    print("tekan P -> alat:", w.tool, "| bentuk:", cv.shape_kind, "| grup Perbaikan:", w.tool_groups["heal"].current,
          "aktif", w.tool_groups["heal"].isChecked(), flush=True)
    got = []
    cv.region_done.connect(lambda *a: got.append(a))

    def closer():                             # tutup menu area yang muncul setelah seleksi
        m = QApplication.activePopupWidget()
        if m:
            print("menu area muncul:", [x.text() for x in m.actions() if x.text()][:6], flush=True)
            m.close()
    ct = QTimer()
    ct.setInterval(250)
    ct.timeout.connect(closer)
    ct.start()

    def drag(mod, dx, dy):
        c = QPoint(cv.viewport().width() // 3, cv.viewport().height() // 3)

        def me(kind, pt, btns):
            return QMouseEvent(kind, _PF(pt), _PF(cv.viewport().mapToGlobal(pt)),
                               Qt.LeftButton if kind != _E.MouseMove else Qt.NoButton, btns, mod)
        QApplication.sendEvent(cv.viewport(), me(_E.MouseButtonPress, c, Qt.LeftButton))
        for k in range(1, 7):
            QApplication.sendEvent(cv.viewport(), me(_E.MouseMove, c + QPoint(dx * k // 6, dy * k // 6), Qt.LeftButton))
            pump(0.02)
        QApplication.sendEvent(cv.viewport(), me(_E.MouseButtonRelease, c + QPoint(dx, dy), Qt.NoButton))
        pump(1.4)
    drag(Qt.NoModifier, 120, 60)
    drag(Qt.ShiftModifier, 120, 60)
    for i, a in enumerate(got):
        print("seleksi", i + 1, "->", [type(x).__name__ for x in a],
              [list(x) if isinstance(x, (list, tuple)) else x for x in a][:2], flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "shots")
