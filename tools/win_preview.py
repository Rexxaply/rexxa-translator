"""Windows asli: reproduksi export (semua format) lewat alur aplikasi (dev)."""
import faulthandler
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
faulthandler.enable(all_threads=True)
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui import main_window as mw
    from gui import exportdlg
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

    d = Path(tempfile.mkdtemp())
    pages = []
    for k in range(3):
        img = np.full((1600, 900, 3), 235, np.uint8)
        cv2.ellipse(img, (450, 400), (230, 140), 0, 0, 360, (0, 0, 0), 4)
        cv2.putText(img, "HELLO", (350, 420), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 5)
        cv2.imwrite(str(d / f"{k:02d}.png"), img)
        bl = [TextBlock(x=230, y=270, w=440, h=260, source="HELLO", translation=f"Halo {k}", src_h=28)]
        pages.append(Page(path=str(d / f"{k:02d}.png"), blocks=bl))
    logo = np.zeros((200, 400, 4), np.uint8)
    logo[..., 1] = 200
    logo[..., 3] = 255
    cv2.imwrite(str(d / "logo.png"), logo)
    f = str(d / "t.mtproj")
    Project(pages=pages, source_lang="en", target_lang="id").save(f)
    w._load_project(f)
    pump(1.0)
    # terjemahkan/render semua halaman dulu (seperti pengguna)
    w._place_image_layer(str(d / "logo.png"))
    pump(0.5)
    w.cur = 0
    from PySide6.QtCore import QPointF
    w._add_text_at(QPointF(100, 900))
    pump(0.3)
    if w.sel is not None and getattr(w.sel, "note", False):
        w.e_tr.setPlainText("catatan bebas")
    pump(0.3)
    for i in range(len(w.project.pages)):
        w.cur = i
        w._show_current()
        w.render_current()
        for _ in range(300):
            if not w.thread:
                break
            pump(0.1)
    print("render selesai, output:", [bool(p.output_path) for p in w.project.pages], flush=True)

    out_dir = d / "out"
    out_dir.mkdir()
    for fmt in ("pdf", "cbz", "zip", "psd", "img"):
        target = str(out_dir / f"hasil_{fmt}") + {"pdf": ".pdf", "cbz": ".cbz", "zip": ".zip", "psd": ".zip"}.get(fmt, "")
        if fmt == "img":
            target = str(out_dir / "gambar")
            Path(target).mkdir()
        QFileDialog.getSaveFileName = staticmethod(lambda *a, t=target, **k: (t, ""))
        QFileDialog.getExistingDirectory = staticmethod(lambda *a, t=target, **k: t)
        orig_exec = exportdlg.ExportDialog.exec

        def auto_exec(self, fmt=fmt):
            i = self.fmt.findData(fmt)
            if i >= 0:
                self.fmt.setCurrentIndex(i)
            QTimer.singleShot(300, self._do_export)      # klik Export cepat (pratinjau masih dimuat)
            return orig_exec(self)
        exportdlg.ExportDialog.exec = auto_exec
        print(f"--- export {fmt} ...", flush=True)
        t0 = time.time()
        try:
            w.export_as()
        except Exception as e:
            print("  EXCEPTION:", repr(e), flush=True)
        for _ in range(600):
            if not w.thread:
                break
            pump(0.1)
        exportdlg.ExportDialog.exec = orig_exec
        out = list(out_dir.rglob("*"))
        print(f"  selesai {time.time() - t0:.1f}s, file:", [(p.name, p.stat().st_size) for p in out if p.is_file()][-4:],
              flush=True)
        print("  log terakhir:", ascii(w.logbox.toPlainText().splitlines()[-2:]), flush=True)
    print("SEMUA SELESAI, aplikasi masih hidup", flush=True)


if __name__ == "__main__":
    main()
