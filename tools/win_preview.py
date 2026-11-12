"""Windows asli: uji Pilih semua balon (dev)."""
import base64
import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
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

    def shot(name):
        w.grab().save(f"{name}.png")
        print("===B64===", name)
        print(base64.b64encode(Path(f"{name}.png").read_bytes()).decode())
        print("===END===", flush=True)

    d = Path(tempfile.mkdtemp())
    img = np.full((1300, 900, 3), 235, np.uint8)
    blocks = []
    for k in range(5):
        cv2.ellipse(img, (450, 140 + k * 250), (200, 90), 0, 0, 360, (0, 0, 0), 3)
        blocks.append(TextBlock(x=260, y=60 + k * 250, w=380, h=160, source="HI", translation=f"Halo {k}"))
    blocks.append(TextBlock(x=40, y=20, w=200, h=60, kind="free", note=True, clean=False, translation="catatan"))
    cv2.imwrite(str(d / "a.png"), img)
    f = str(d / "t.mtproj")
    Project(pages=[Page(path=str(d / "a.png"), blocks=blocks)], source_lang="en", target_lang="id").save(f)
    w._load_project(f)
    pump(1.0)
    if not w.insp_slide.open:
        w.toggle_inspector(True)
        pump(1.0)
    print("tanpa pilihan: tombol atas", w.b_sel_all_top.isVisible(), flush=True)
    shot("s0_kosong")
    w._select(w.page().blocks[1])
    pump(0.3)
    print("1 dipilih: tombol di kartu Balon", w.b_sel_all.isVisible(), "hapus:", w.b_del.text(), flush=True)
    shot("s1_satu")
    w.b_sel_all.click()
    pump(0.5)
    print("Pilih semua: terpilih", len(w._targets()), "multi bar", w.multi_bar.isVisible(),
          "tombol", w.b_sel_all.isVisible(), "hapus:", w.b_del.text(), flush=True)
    shot("s2_semua")
    w._select(None)
    pump(0.2)
    w.cv_src.setFocus()
    pump(0.2)
    QTest.keyClick(w.cv_src, Qt.Key_A, Qt.ControlModifier)
    pump(0.4)
    print("Ctrl+A: terpilih", len(w._targets()), flush=True)
    w.b_del.click()
    pump(0.6)
    print("setelah hapus: sisa", [(b.kind, b.note) for b in w.page().blocks], flush=True)
    w.undo()
    pump(0.5)
    print("undo: jumlah", len(w.page().blocks), flush=True)


if __name__ == "__main__":
    main()
