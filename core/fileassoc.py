"""Windows: daftarkan file proyek .mtproj ke Rexxa Translator (ikon file + buka dengan klik ganda).

Ditulis di HKEY_CURRENT_USER (tanpa hak admin), diperbarui setiap aplikasi dibuka bila lokasi
aplikasi / ikon berubah. Tidak melakukan apa-apa di luar Windows atau saat dijalankan dari kode sumber.
"""
from __future__ import annotations

import os
import sys

from . import paths

EXT = ".mtproj"
PROGID = "RexxaTranslator.Project"


def register(force: bool = False) -> bool:
    if not sys.platform.startswith("win") or not paths.is_frozen():
        return False
    try:
        import winreg
    except ImportError:
        return False
    exe = sys.executable
    ico = paths.code_dir() / "assets" / "project.ico"
    if not ico.exists():
        ico = paths.code_dir() / "assets" / "icon.ico"
    want = {
        rf"Software\Classes\{EXT}": {"": PROGID, "Content Type": "application/x-rexxa-project"},
        rf"Software\Classes\{PROGID}": {"": "Proyek Rexxa Translator"},
        rf"Software\Classes\{PROGID}\DefaultIcon": {"": f'"{ico}"'},
        rf"Software\Classes\{PROGID}\shell\open": {"": "Buka dengan Rexxa Translator"},
        rf"Software\Classes\{PROGID}\shell\open\command": {"": f'"{exe}" "%1"'},
    }
    changed = False
    try:
        for key, values in want.items():
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ | winreg.KEY_WRITE) as k:
                for name, val in values.items():
                    try:
                        cur, _t = winreg.QueryValueEx(k, name)
                    except OSError:
                        cur = None
                    if force or cur != val:
                        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
                        changed = True
        # OpenWithProgids: muncul di menu "Buka dengan"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{EXT}\OpenWithProgids", 0,
                                winreg.KEY_WRITE) as k:
            winreg.SetValueEx(k, PROGID, 0, winreg.REG_NONE, b"")
    except OSError:
        return False
    if changed:
        try:   # minta Explorer memperbarui ikon file
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass
    return changed


def register_async():
    import threading
    threading.Thread(target=lambda: register(), daemon=True).start()
