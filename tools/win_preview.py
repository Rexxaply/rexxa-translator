"""Windows asli: cari jendela 'hantu' yang muncul sebelum pop-up Pengaturan (dev)."""
import ctypes
import os
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image, ImageGrab  # noqa: E402
from PySide6.QtCore import QEvent, QObject, Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

user32 = ctypes.windll.user32
PID = os.getpid()


def native_windows():
    res = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _l):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value == PID and user32.IsWindowVisible(h):
            r = wintypes.RECT()
            user32.GetWindowRect(h, ctypes.byref(r))
            buf = ctypes.create_unicode_buffer(200)
            user32.GetWindowTextW(h, buf, 200)
            cls = ctypes.create_unicode_buffer(200)
            user32.GetClassNameW(h, cls, 200)
            style = user32.GetWindowLongW(h, -16)
            res.append((int(h or 0), buf.value, cls.value, hex(style & 0xFFFFFFFF),
                        (r.left, r.top, r.right - r.left, r.bottom - r.top)))
        return True
    user32.EnumWindows(cb, 0)
    return res


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    from gui import main_window as mw
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui.glass import install_popup_fx
    install_popup_fx(app)
    app.setStyleSheet(mw.STYLE)
    w = mw.MainWindow()
    w.resize(1300, 820)
    w.move(40, 20)
    w.show()
    t_end = time.time() + 2.0
    while time.time() < t_end:
        app.processEvents()
        time.sleep(0.01)
    base = {x[0] for x in native_windows()}
    print("jendela awal:", native_windows(), flush=True)
    T0 = [time.perf_counter()]
    log = []

    class Spy(QObject):
        def eventFilter(self, o, e):
            t = e.type()
            if t in (QEvent.Show, QEvent.Hide, QEvent.WinIdChange) and o.isWidgetType() and o.isWindow():
                log.append((round((time.perf_counter() - T0[0]) * 1000), str(t).split(".")[-1], type(o).__name__,
                            o.objectName(), o.metaObject().className(), hex(int(o.windowFlags())),
                            o.testAttribute(Qt.WA_DontShowOnScreen), o.geometry().getRect(), o.windowTitle()))
            return False
    spy = Spy()
    app.installEventFilter(spy)
    seen = {}
    shots = []
    stop = [False]

    def watcher():
        while not stop[0]:
            ms = round((time.perf_counter() - T0[0]) * 1000)
            for x in native_windows():
                if x[0] not in base:
                    seen.setdefault((x[0], x[1], x[2], x[3], x[4]), ms)
            time.sleep(0.002)

    def grabber():
        g = w.frameGeometry()
        box = (g.left(), g.top(), g.right(), g.bottom())
        while not stop[0]:
            shots.append((round((time.perf_counter() - T0[0]) * 1000), ImageGrab.grab(bbox=box, all_screens=True)))

    def finish():
        stop[0] = True
        print("EVENT jendela Qt:", flush=True)
        for row in log:
            print("  ", row, flush=True)
        print("JENDELA NATIVE BARU (pertama terlihat ms):", flush=True)
        for k, v in sorted(seen.items(), key=lambda kv: kv[1]):
            print("  ", v, k, flush=True)
        sel = [s for s in shots if s[0] < 900][:16]
        sw, sh = 520, 330
        sheet = Image.new("RGB", (sw * 4, sh * 4), "black")
        for i, (ms, im) in enumerate(sel):
            sheet.paste(im.resize((sw, sh)), ((i % 4) * sw, (i // 4) * sh))
        sheet.save(out / "3_pengaturan_buka.png")
        print("foto ms:", [s[0] for s in sel], flush=True)
        os._exit(0)

    def go():
        T0[0] = time.perf_counter()
        threading.Thread(target=watcher, daemon=True).start()
        threading.Thread(target=grabber, daemon=True).start()
        QTimer.singleShot(1500, finish)
        from gui.alert import Alert
        from gui.dialogs import NameDialog
        Alert(w, "Tes", "Judul", "detail", kind="warn")
        NameDialog(w, "Nama", "x")
        log.append(("--- setelah Alert & NameDialog dibuat ---",))
        w.edit_settings()
    QTimer.singleShot(100, go)
    app.exec()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "shots")
