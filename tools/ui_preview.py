"""Cek: efek bawaan dropdown & menu mati (dev)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def main(out):
    Path(out).mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    E = Qt.UIEffect
    for e in (E.UI_AnimateCombo, E.UI_AnimateMenu, E.UI_FadeMenu):
        app.setEffectEnabled(e, True)               # paksa nyala dulu seperti di Windows
    print("sebelum:", [QApplication.isEffectEnabled(e) for e in (E.UI_AnimateCombo, E.UI_AnimateMenu, E.UI_FadeMenu)], flush=True)
    from gui.glass import install_popup_fx
    install_popup_fx(app)
    print("sesudah:", [QApplication.isEffectEnabled(e) for e in (E.UI_AnimateCombo, E.UI_AnimateMenu, E.UI_FadeMenu)], flush=True)
    print("ok", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ui_preview")
