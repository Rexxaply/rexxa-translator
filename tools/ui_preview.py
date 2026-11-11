"""Tangkapan layar daftar font berpratinjau (dev)."""
import glob
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["XDG_CONFIG_HOME"] = str(Path(tempfile.mkdtemp()) / "cfg")

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget  # noqa: E402


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    from gui import main_window as mw
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from gui import uifonts
    uifonts.load()
    app.setStyleSheet(mw.STYLE)
    from gui.fontcombo import FontCombo
    fonts = sorted(set(glob.glob("/usr/share/fonts/truetype/**/*.ttf", recursive=True)))
    want = [f for f in fonts if any(k in f for k in ("ComicNeue", "Liberation", "Ubuntu", "DejaVuSerif", "FiraCode",
                                                      "Dancing", "Lobster", "Pacifico", "Caveat"))][:28]
    want += sorted(glob.glob("assets/ui_fonts/*.ttf"))
    print(len(want), flush=True)
    w = QWidget()
    w.resize(320, 60)
    lay = QVBoxLayout(w)
    c = FontCombo()
    c.addItem("Font default", "")
    from core import typeset
    for f in want:
        c.addItem(typeset.font_name(f), f)
    lay.addWidget(c)
    w.show()
    for _ in range(100):
        app.processEvents()
    c.showPopup()
    for _ in range(300):
        app.processEvents()
    c.view().window().grab().save(str(out / "1_font_popup.png"))
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
