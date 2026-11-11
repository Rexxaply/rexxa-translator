"""Uji menu & dropdown frosted (dev)."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen:size=1600x1000")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
tmp = Path(tempfile.mkdtemp())
os.environ["XDG_CONFIG_HOME"] = str(tmp / "cfg")
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def pump(app, sec):
    t = time.time()
    while time.time() - t < sec:
        app.processEvents()
        time.sleep(0.004)


def pil(q):
    q = q.convertToFormat(q.Format.Format_RGBA8888)
    return Image.frombuffer("RGBA", (q.width(), q.height()), bytes(q.constBits()), "raw", "RGBA", q.bytesPerLine(), 1).copy()


def compose(main, *wins):
    base = pil(main.grab().toImage())
    o = main.mapToGlobal(QPoint(0, 0))
    for w in wins:
        if w is not None and w.isVisible():
            p = w.mapToGlobal(QPoint(0, 0)) - o
            base.alpha_composite(pil(w.grab().toImage()), (max(0, p.x()), max(0, p.y())))
    return base.convert("RGB")


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    from gui import main_window as mw
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui import uifonts
    uifonts.load()
    from gui.glass import install_popup_fx
    install_popup_fx(app)
    app.setStyleSheet(mw.STYLE)
    w = mw.MainWindow()
    w.resize(780, 560)
    w.move(0, 0)
    w.show()
    d = tmp / "ch"
    d.mkdir()
    rng = np.random.default_rng(3)
    for n in range(1, 3):
        im = np.zeros((900, 640, 3), np.uint8)
        for _ in range(16):
            c = tuple(int(x) for x in rng.integers(40, 255, 3))
            cv2.circle(im, (int(rng.integers(0, 640)), int(rng.integers(0, 900))), int(rng.integers(60, 200)), c, -1)
        cv2.imwrite(str(d / f"{n:03d}.png"), im)
    w._load_paths([str(d)])
    pump(app, 1.5)
    w._fill_engine_menu()
    m = w.b_go.menu()
    m.popup(w.mapToGlobal(QPoint(170, 50)))
    pump(app, 0.5)
    print("menu: latar frosted ada =", getattr(m, "_fx_bd", None) is not None, flush=True)
    compose(w, m).save(out / "1_menu_frosted.png")
    m.hide()
    pump(app, 0.2)
    w.src.showPopup()
    pump(app, 0.5)
    c = w.src.view().window()
    print("dropdown: latar frosted ada =", getattr(c, "_fx_bd", None) is not None, flush=True)
    from gui.glass import _PopupFx, frosted
    h = _PopupFx._host_of(c)
    print("debug: kelas =", c.metaObject().className(), "| fx =", c.property("_rexxa_fx"), "| parent =",
          c.parentWidget().metaObject().className() if c.parentWidget() else None, "| host =",
          h.metaObject().className() if h else None, "| geo =", c.geometry(), flush=True)
    if h is not None:
        import traceback
        try:
            from PySide6.QtCore import QRect
            g = c.geometry()
            tl = h.mapFromGlobal(g.topLeft())
            print("debug rect:", QRect(tl.x() - 24, tl.y() - 24, g.width() + 48, g.height() + 48), flush=True)
            print("debug frosted:", frosted(h, QRect(tl.x() - 24, tl.y() - 24, g.width() + 48, g.height() + 48), 5.0), flush=True)
        except Exception:
            traceback.print_exc()
    compose(w, c).save(out / "2_dropdown_frosted.png")
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
