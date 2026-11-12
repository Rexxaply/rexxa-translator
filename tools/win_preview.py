"""Windows asli: ukur kecepatan bagian-bagian aplikasi (dev)."""
import cProfile
import io
import os
import pstats
import sys
import tempfile
import time
from pathlib import Path

T_START = time.perf_counter()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    t = time.perf_counter()
    from gui import main_window as mw
    from core.models import Page, Project, TextBlock
    print(f"import modul: {(time.perf_counter() - t) * 1000:.0f} ms", flush=True)
    from gui.glass import install_popup_fx, install_smooth_scroll
    install_popup_fx(app)
    install_smooth_scroll(app)
    app.setStyleSheet(mw.STYLE)

    def pump(s=0.05):
        t = time.time()
        while time.time() - t < s:
            app.processEvents()
            time.sleep(0.001)

    def timed(name, fn, prof=False):
        pr = cProfile.Profile() if prof else None
        t = time.perf_counter()
        if pr:
            pr.enable()
        r = fn()
        app.processEvents()
        if pr:
            pr.disable()
        ms = (time.perf_counter() - t) * 1000
        print(f"{name}: {ms:.0f} ms", flush=True)
        if pr and ms > 80:
            s = io.StringIO()
            pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(18)
            for ln in s.getvalue().splitlines()[6:32]:
                print("   ", ln[:150], flush=True)
        return r

    from PySide6.QtWidgets import QComboBox, QLineEdit, QLabel
    timed("uji: QLabel pertama", lambda: QLabel("tes").sizeHint())
    timed("uji: QLineEdit pertama", lambda: QLineEdit().sizeHint())
    timed("uji: QComboBox editable", lambda: QComboBox().setEditable(True))
    from PySide6.QtGui import QFontDatabase
    timed("uji: QFontDatabase.families()", lambda: len(QFontDatabase.families()))
    w = timed("bangun jendela utama", lambda: mw.MainWindow(), prof=True)
    w.resize(1280, 800)
    timed("tampilkan jendela", w.show)
    pump(0.5)
    # proyek 30 halaman tinggi (webtoon) dengan 8 balon per halaman, sudah 'selesai'
    d = Path(tempfile.mkdtemp())
    pages = []
    for i in range(30):
        img = np.full((3000, 800, 3), 235, np.uint8)
        for k in range(8):
            cy = 200 + k * 350
            cv2.ellipse(img, (400, cy), (220, 130), 0, 0, 360, (0, 0, 0), 4)
            cv2.putText(img, "HELLO THERE", (260, cy + 10), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 3)
        p_ = d / f"{i:02d}.png"
        cv2.imwrite(str(p_), img)
        cl = img.copy()
        cl[cl < 128] = 235
        cv2.imwrite(str(d / f"{i:02d}_c.png"), cl)
        pages.append(Page(path=str(p_), status="selesai", cleaned_path=str(d / f"{i:02d}_c.png"),
                          blocks=[TextBlock(x=230, y=130 + k * 350, w=340, h=140, source="HELLO THERE",
                                            translation=f"Halo di sana {k}", src_h=28,
                                            text_rect=[250, 160 + k * 350, 300, 80]) for k in range(8)]))
    f = str(d / "big.mtproj")
    Project(pages=pages, source_lang="en", target_lang="id").save(f)
    timed("buka proyek 30 halaman", lambda: w._load_project(f), prof=True)
    t_ = time.time()
    first = w.pages.item(29).icon().cacheKey()
    while time.time() - t_ < 5 and w.pages.item(29).icon().cacheKey() == first:
        pump(0.02)
    print(f"thumbnail semua halaman siap dalam {(time.time() - t_) * 1000:.0f} ms (latar, tampilan tetap responsif)",
          "| ukuran ikon", w.pages.item(29).icon().availableSizes(), flush=True)
    pump(1.0)
    timed("render halaman 1 (penuh)", lambda: (w.render_current(), [pump(0.05) for _ in range(400) if w.thread]))
    pump(1.0)
    for i in (1, 2, 3):
        timed(f"pindah ke halaman {i + 1}", lambda i=i: w.pages.setCurrentRow(i), prof=(i == 1))
        pump(0.3)
    w.pages.setCurrentRow(0)
    pump(0.5)
    p = w.page()
    timed("pilih balon", lambda: w._select(p.blocks[3]), prof=True)
    timed("pilih balon lain", lambda: w._select(p.blocks[5]), prof=True)
    w.e_tr.setFocus()
    from PySide6.QtTest import QTest
    lat = []
    for ch in "Tes cepat":
        t = time.perf_counter()
        QTest.keyClicks(w.e_tr, ch)
        app.processEvents()
        lat.append((time.perf_counter() - t) * 1000)
        pump(0.08)
    print("ketik (waktu di thread tampilan per huruf, ms):", [round(x) for x in lat], flush=True)
    pump(1.5)
    timed("buka Pengaturan (konstruksi dialog)", lambda: __import__("gui.dialogs", fromlist=["x"]).SettingsDialog(
        w.settings, w, project=w.project), prof=True)
    timed("ganti tab Balon", lambda: w.tabs.setCurrentIndex(1))
    timed("ganti tab Properti", lambda: w.tabs.setCurrentIndex(0))
    timed("sembunyikan panel (mulai animasi)", lambda: w.toggle_inspector(False))
    pump(0.6)
    timed("simpan proyek", lambda: w.project.save(f), prof=True)
    print(f"total sejak mulai: {(time.perf_counter() - T_START):.1f} s", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
