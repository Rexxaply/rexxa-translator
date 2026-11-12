"""Windows asli: uji zoom, panel, dan lapisan gambar (dev)."""
import base64
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
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui import main_window as mw
    from gui.glass import install_popup_fx, install_smooth_scroll
    from core.models import Page, Project
    install_popup_fx(app)
    install_smooth_scroll(app)
    app.setStyleSheet(mw.STYLE)
    w = mw.MainWindow()
    w.resize(1000, 700)
    w.show()

    def pump(t):
        e = time.time() + t
        while time.time() < e:
            app.processEvents()
            time.sleep(0.002)

    def shot(name):
        pm = w.grab()
        pm.save(f"{name}.png")
        print("===B64===", name)
        print(base64.b64encode(Path(f"{name}.png").read_bytes()).decode())
        print("===END===", flush=True)

    def P(pt):
        return (round(pt.x()), round(pt.y()))

    d = Path(tempfile.mkdtemp())
    img = np.full((4000, 900, 3), 235, np.uint8)
    for k in range(10):
        cv2.putText(img, f"ROW {k}", (300, 200 + k * 380), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 4)
        cv2.line(img, (0, 380 * k), (900, 380 * k), (180, 180, 200), 3)
    cv2.imwrite(str(d / "a.png"), img)
    logo = np.zeros((220, 500, 4), np.uint8)
    cv2.rectangle(logo, (0, 0), (499, 219), (60, 40, 230, 255), -1)
    cv2.putText(logo, "CHAPTER 12", (30, 135), cv2.FONT_HERSHEY_DUPLEX, 2.0, (255, 255, 255, 255), 4)
    cv2.imwrite(str(d / "logo.png"), logo)
    pg = Page(path=str(d / "a.png"))
    f = str(d / "t.mtproj")
    Project(pages=[pg], source_lang="en", target_lang="id").save(f)
    w._load_project(f)
    pump(1.0)
    if not w.insp_slide.open:
        w.toggle_inspector(True)
        pump(1.0)
    cv = w.cv_src
    vp = cv.viewport()
    print("strip", cv.is_strip(), "zoom", round(cv.zoom(), 3), flush=True)

    # 1) buka/tutup panel di tengah strip -> posisi baca tetap
    cv.verticalScrollBar().setValue(cv.verticalScrollBar().maximum() // 2)
    pump(0.3)
    c0 = cv.mapToScene(vp.rect().center())
    w.toggle_inspector(False)
    pump(1.0)
    c1 = cv.mapToScene(vp.rect().center())
    print("PANEL tutup: tengah sebelum", P(c0), "sesudah", P(c1), "zoom", round(cv.zoom(), 3), flush=True)
    w.toggle_inspector(True)
    pump(1.0)
    c2 = cv.mapToScene(vp.rect().center())
    print("PANEL buka: tengah", P(c2), "zoom", round(cv.zoom(), 3), flush=True)

    # 2) tombol zoom -> tetap di tengah
    c3a = cv.mapToScene(vp.rect().center())
    w._zoom_step(1.25)
    pump(0.2)
    c3 = cv.mapToScene(vp.rect().center())
    print("TOMBOL +: tengah sebelum", P(c3a), "sesudah", P(c3), "zoom", round(cv.zoom(), 3), flush=True)
    w._zoom_step(1 / 1.25)
    pump(0.2)
    print("TOMBOL -: tengah", P(cv.mapToScene(vp.rect().center())), flush=True)
    # panel toggle setelah zoom manual: zoom tidak di-reset
    z_before = cv.zoom()
    w._zoom_step(1.25)
    pump(0.2)
    z_before = cv.zoom()
    w.toggle_inspector(False)
    pump(1.0)
    print("PANEL setelah zoom manual: zoom", round(z_before, 3), "->", round(cv.zoom(), 3), flush=True)
    w.toggle_inspector(True)
    pump(1.0)

    # 3) roda mouse -> zoom ke arah kursor
    for fx, fy, dy in ((0.8, 0.25, 120), (0.2, 0.8, 120), (0.7, 0.6, -120)):
        pos = QPointF(vp.width() * fx, vp.height() * fy)
        before = cv.mapToScene(pos.toPoint())
        ev = QWheelEvent(pos, vp.mapToGlobal(pos), QPoint(0, 0), QPoint(0, dy), Qt.NoButton, Qt.NoModifier,
                         Qt.ScrollUpdate, False)
        cv.wheelEvent(ev)
        pump(0.15)
        after = cv.mapToScene(pos.toPoint())
        print(f"RODA {dy:+d} di ({fx},{fy}): di bawah kursor", P(before), "->", P(after), "zoom",
              round(cv.zoom(), 3), "| Hasil zoom", round(w.cv_out.zoom(), 3), flush=True)

    # 4) perkecil jauh -> gambar di tengah
    for _ in range(14):
        w._zoom_step(1 / 1.25)
    pump(0.3)
    r = cv.mapFromScene(cv.sceneRect()).boundingRect()
    print("PERKECIL: gambar", (r.x(), r.y(), r.width(), r.height()), "viewport", (vp.width(), vp.height()),
          "kiri/kanan", r.x(), vp.width() - r.right(), flush=True)
    shot("z1_perkecil")
    w._fit_both()
    pump(0.3)
    cv.verticalScrollBar().setValue(cv.verticalScrollBar().maximum() // 3)
    pump(0.3)

    # 5) lapisan gambar
    w._place_image_layer(str(d / "logo.png"))
    pump(2.5)
    p = w.page()
    b = p.blocks[-1]
    print("LAPISAN", b.kind, (b.x, b.y, b.w, b.h), "terpilih", w.sel is b, "panel gambar", w.img_box.isVisible(),
          "kartu lain", [s.isVisible() for s in w.sections], "judul", w.sections[3].btn.text(), flush=True)
    for _ in range(40):
        if p.output_path and Path(p.output_path).exists():
            break
        pump(0.1)
    print("hasil", bool(p.output_path), flush=True)
    pump(1.0)
    out = cv2.imread(p.output_path) if p.output_path else None
    if out is not None:
        print("piksel tengah lapisan", out[b.y + 30, b.x + 8].tolist(), "luar", out[5, 5].tolist(), flush=True)
    shot("z2_lapisan")
    w.p_opacity.setValue(50)
    pump(2.0)
    print("opasitas", b.opacity, flush=True)
    out = cv2.imread(p.output_path)
    if out is not None:
        print("piksel 50%", out[b.y + 30, b.x + 8].tolist(), flush=True)
    # geser lapisan
    b.x += 120
    b.y += 60
    w._on_geom_changed(b)
    pump(2.5)
    out = cv2.imread(p.output_path)
    if out is not None:
        print("setelah geser: piksel", out[b.y + 30, b.x + 8].tolist(), flush=True)
    shot("z3_geser")
    w.undo()
    pump(1.0)
    print("undo -> posisi", (p.blocks[-1].x, p.blocks[-1].y), "opasitas", p.blocks[-1].opacity, flush=True)
    w._select(None)
    pump(0.5)
    print("lepas pilihan: kartu", [s.isVisible() for s in w.sections], "panel gambar", w.img_box.isVisible(), flush=True)


if __name__ == "__main__":
    main()
