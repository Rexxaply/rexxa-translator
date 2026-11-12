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
    w.resize(1280, 860)
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
    pump(1.0)
    # 4 proyek di riwayat
    import random
    from core.models import Page, Project
    import time as _t
    names = [("Reincarnated as a Villainous Duke", 18, 7), ("Solo Leveling Ch. 112", 22, 22),
             ("Oshi no Ko Ch. 140", 16, 3), ("test1", 1, 1)]
    for k, (nm, n, done) in enumerate(names):
        dd = Path(tempfile.mkdtemp())
        pages = []
        for i in range(min(n, 3)):
            img = np.full((1300, 900, 3), 245, np.uint8)
            rnd = random.Random(k * 10 + i)
            col = (rnd.randint(40, 200), rnd.randint(40, 200), rnd.randint(40, 200))
            cv2.rectangle(img, (40, 40), (860, 600), col, -1)
            cv2.circle(img, (450, 330), 170, (250, 250, 250), -1)
            cv2.rectangle(img, (40, 650), (430, 1260), (60, 60, 70), -1)
            cv2.ellipse(img, (660, 930), (180, 120), 0, 0, 360, (20, 20, 20), 4)
            fp = dd / f"p{i + 1}.png"
            cv2.imwrite(str(fp), img)
            pages.append(Page(path=str(fp), status="selesai" if i < done else "baru"))
        for i in range(len(pages), n):
            pages.append(Page(path=str(dd / f"p{i + 1}.png"), status="selesai" if i < done else "baru"))
        proj = Project(pages=pages, source_lang="ja" if k != 3 else "en", target_lang="id")
        fpj = str(dd / f"{nm}.mtproj")
        proj.save(fpj)
        w._add_recent(fpj)
        _t.sleep(0.05)
    w._show_recent()
    pump(1.5)
    shot("0_awal.png")
    print("riwayat tersimpan:", len(w.settings.get("recent_projects") or []), flush=True)
    # gambaran di jendela besar (tidak dibatasi layar runner 1024x720)
    w2 = mw.MainWindow()
    w2.setAttribute(Qt.WA_DontShowOnScreen, True)
    w2.resize(1440, 900)
    w2.show()
    pump(0.5)
    w2._show_recent()
    pump(1.5)
    w2.grab().save(str(out / "0_awal_besar.png"))
    w2.close()

    w._load_project(f)
    pump(1.0)
    w.render_current()
    t = time.time()
    while w.thread and time.time() - t < 30:
        pump(0.05)
    pump(1.0)
    p = w.page()
    print("strip halaman: mode", w.pages.viewMode(), "gerak", w.pages.movement(), flush=True)
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
    # ---- pintasan grup & Ctrl+Shift, Pen terpisah, alat Teks
    w.activateWindow()
    cv = w.cv_src
    cv.setFocus()
    pump(0.3)

    def st():
        return (w.tool, w.tool_groups["heal"].current, w.tool_groups["shape"].current, w.g_box.current,
                [n for n, g in w.tool_groups.items() if g.isChecked()] + (["box"] if w.g_box.isChecked() else []))
    for keys, mod in ((Qt.Key_J, Qt.NoModifier), (Qt.Key_J, Qt.ControlModifier | Qt.ShiftModifier),
                      (Qt.Key_J, Qt.NoModifier), (Qt.Key_J, Qt.ControlModifier | Qt.ShiftModifier),
                      (Qt.Key_A, Qt.NoModifier), (Qt.Key_A, Qt.ControlModifier | Qt.ShiftModifier),
                      (Qt.Key_B, Qt.NoModifier), (Qt.Key_B, Qt.ControlModifier | Qt.ShiftModifier),
                      (Qt.Key_P, Qt.NoModifier), (Qt.Key_T, Qt.NoModifier)):
        QTest.keyClick(cv, keys, mod)
        pump(0.25)
        cv.setFocus()
        print("tombol", ("Ctrl+Shift+" if mod != Qt.NoModifier else "") + chr(keys), "->", st(), flush=True)
    # alat Teks: klik tempat kosong -> teks baru, langsung ketik
    n0 = len(p.blocks)
    from PySide6.QtCore import QPointF as _PF
    w.set_tool("text")
    cv.text_click.emit(_PF(450, 2530))
    pump(0.4)
    QTest.keyClicks(QApplication.focusWidget(), "Catatan TL: ini nama tempat")
    pump(1.2)
    nb = p.blocks[-1]
    print("teks bebas:", len(p.blocks) - n0, "baru | fokus", type(QApplication.focusWidget()).__name__,
          "| isi", repr(nb.translation), "| hapus latar", nb.clean, "| jenis", nb.kind, flush=True)
    pump(0.5)
    shot("5_teks_bebas.png")
    print("panel teks:", w.sections[0].btn.text(), "|", w.sections[0].chip.text(), "| OCR terlihat", w.b_reocr.isVisible(),
          "| ukuran", w.p_size.text(), "| hapus", w.b_del.text(), "| catatan", nb.note, flush=True)
    w._select(p.blocks[1])
    pump(0.6)
    shot("5b_panel_balon.png")
    print("panel balon:", w.sections[0].btn.text(), "|", w.sections[0].chip.text(), "| OCR terlihat", w.b_reocr.isVisible(),
          "| ukuran", w.p_size.text(), flush=True)
    w.tool_groups["heal"].show_menu if False else None
    def grab_heal():
        pump(0.5)
        m = QApplication.activePopupWidget()
        shot("6_grup_perbaikan.png", popup=m)
        if m:
            m.close()
    QTimer.singleShot(0, grab_heal)
    w.tool_groups["heal"].show_menu()
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "shots")
