"""Windows asli: uji tab Gambar + hapus latar (dev)."""
import base64
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDragEnterEvent, QDropEvent  # noqa: E402
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
    w.resize(1020, 720)
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

    d = Path(tempfile.mkdtemp())
    page = np.full((1300, 900, 3), 235, np.uint8)
    for k in range(4):
        cv2.putText(page, f"PANEL {k}", (300, 200 + k * 320), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 4)
        cv2.rectangle(page, (40, 40 + k * 320), (860, 300 + k * 320), (60, 60, 60), 4)
    cv2.imwrite(str(d / "a.png"), page)
    # layar hijau tidak rata + objek merah berisi tulisan putih
    g = np.zeros((300, 520, 3), np.uint8)
    g[:] = (40, 185, 30)
    g[..., 1] = np.clip(g[..., 1].astype(int) + (np.arange(520) % 40), 0, 255).astype(np.uint8)
    cv2.circle(g, (260, 150), 120, (40, 40, 220), -1)
    cv2.putText(g, "CH.12", (165, 172), cv2.FONT_HERSHEY_DUPLEX, 2.0, (255, 255, 255), 5)
    cv2.imwrite(str(d / "green.png"), g)
    # logo di latar putih (ada putih di dalamnya)
    wb = np.full((220, 460, 3), 255, np.uint8)
    cv2.rectangle(wb, (30, 30), (430, 190), (200, 90, 20), -1)
    cv2.putText(wb, "REXXA", (95, 140), cv2.FONT_HERSHEY_DUPLEX, 2.4, (255, 255, 255), 6)
    cv2.imwrite(str(d / "white.jpg"), wb)
    pg = Page(path=str(d / "a.png"))
    f = str(d / "t.mtproj")
    Project(pages=[pg], source_lang="en", target_lang="id").save(f)
    w._load_project(f)
    pump(1.0)
    if not w.insp_slide.open:
        w.toggle_inspector(True)
        pump(1.0)
    w.tabs.setCurrentWidget(w.img_tab)
    pump(0.5)
    print("tab:", [w.tabs.tabText(i) for i in range(w.tabs.count())], flush=True)
    shot("g0_tab_kosong")

    # seret & lepas 2 file ke kotak
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(str(d / "green.png")), QUrl.fromLocalFile(str(d / "white.jpg"))])
    dz = w.drop_zone
    pos = QPointF(dz.width() / 2, dz.height() / 2)
    ev = QDragEnterEvent(pos.toPoint(), Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
    dz.dragEnterEvent(ev)
    print("drag diterima:", ev.isAccepted(), "sorot:", dz.property("hot"), flush=True)
    dz.dropEvent(QDropEvent(pos, Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier))
    pump(2.0)
    p = w.page()
    lay = [b for b in p.blocks if b.kind == "image"]
    print("lapisan:", [(b.x, b.y, b.w, b.h) for b in lay], "daftar:", w.img_list.count(),
          "tab tetap Gambar:", w.tabs.currentWidget() is w.img_tab, flush=True)
    # hapus latar hijau pada lapisan 1
    w._select(lay[0])
    pump(0.3)
    print("terpilih #1, panel aktif:", w.key_sec.isEnabled(), flush=True)
    w.key_btns["green"].click()
    pump(1.5)
    b = lay[0]
    from PIL import Image
    a = np.asarray(Image.open(b.title_image).convert("RGBA"))
    print("HIJAU: mode", b.key_mode, "alpha latar", int(a[5, 5, 3]), "alpha objek", int(a[150, 260, 3]),
          "alpha tulisan putih", int(a[150, 200, 3]), "info:", w.key_info.text(), flush=True)
    for _ in range(30):
        if p.output_path and Path(p.output_path).exists():
            break
        pump(0.1)
    pump(1.5)
    out = cv2.imread(p.output_path) if p.output_path else None
    if out is not None:
        print("hasil: piksel latar lapisan", out[b.y + 5, b.x + 5].tolist(), "(halaman = 235)",
              "objek", out[b.y + b.h // 2, b.x + b.w // 2].tolist(), flush=True)
    shot("g1_hijau")
    # putih otomatis pada lapisan 2
    b2 = lay[1]
    w._select(b2)
    pump(0.3)
    w.key_btns["auto"].click()
    pump(1.5)
    a2 = np.asarray(Image.open(b2.title_image).convert("RGBA"))
    print("OTOMATIS: alpha latar", int(a2[5, 5, 3]), "kotak", int(a2[50, 50, 3]), "tulisan putih di dalam",
          int(a2[118, 130, 3]), "info:", w.key_info.text(), flush=True)
    w.key_edge.setChecked(False)
    pump(1.0)
    a3 = np.asarray(Image.open(b2.title_image).convert("RGBA"))
    print("tanpa 'hanya tepi': tulisan putih alpha", int(a3[118, 130, 3]), flush=True)
    w.key_edge.setChecked(True)
    pump(1.0)
    w.key_tol.setValue(60, emit=True)
    pump(1.0)
    print("toleransi 60 tersimpan:", b2.key_tol, flush=True)
    pump(1.5)
    shot("g2_otomatis")
    w.key_btns[""].click()
    pump(1.0)
    print("TIDAK: kembali ke asli", b2.title_image == b2.layer_src, flush=True)
    w.undo()
    pump(1.0)
    bb = [x for x in w.page().blocks if x.kind == "image"][1]
    print("undo -> mode", bb.key_mode, flush=True)
    w._select(None)
    pump(0.3)
    print("lepas: panel aktif", w.key_sec.isEnabled(), flush=True)


if __name__ == "__main__":
    main()
