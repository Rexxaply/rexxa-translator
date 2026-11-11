"""Font antarmuka: Inter untuk teks & kontrol, Plus Jakarta Sans untuk judul (SIL OFL, ikut dibundel).

Font ini hanya untuk tampilan aplikasi; tidak muncul di daftar font typesetting."""
from __future__ import annotations

TEXT = "Inter"
HEAD = "Plus Jakarta Sans"
_loaded = False


def load() -> bool:
    """Daftarkan font di assets/ui_fonts. True bila Inter tersedia."""
    global _loaded
    from PySide6.QtGui import QFontDatabase
    if not _loaded:
        from core.paths import code_dir
        d = code_dir() / "assets" / "ui_fonts"
        for f in sorted(d.glob("*.ttf")) if d.exists() else []:
            QFontDatabase.addApplicationFont(str(f))
        _loaded = True
    return TEXT in QFontDatabase.families()
