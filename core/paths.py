"""Lokasi file aplikasi.

- app_dir()  : folder program (tempat .exe / root source). DITIMPA setiap update — jangan simpan data user di sini.
- code_dir() : folder kode aplikasi (berisi core/, gui/, assets/). Di versi .exe ini folder `app/`
               di samping .exe, supaya update rutin cukup mengganti folder ini (kecil & cepat).
- data_dir() : folder data user, AMAN dari update/rebuild.
               Windows: %APPDATA%\\RexxaTranslator   Linux/mac: ~/.config/RexxaTranslator
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_ID = "RexxaTranslator"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):          # saat jadi .exe (PyInstaller)
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def code_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    d = base / APP_ID
    d.mkdir(parents=True, exist_ok=True)
    return d


def user_fonts_dir() -> Path:
    """Font tambahan milik user (tidak hilang saat update)."""
    d = data_dir() / "fonts"
    d.mkdir(exist_ok=True)
    return d


def bundled_fonts_dir() -> Path:
    """Font yang ikut dibagikan bersama aplikasi."""
    return code_dir() / "fonts"


def settings_file() -> Path:
    return data_dir() / "settings.json"


def migrate_old_data():
    """Versi lama menyimpan settings.json & font di folder program — pindahkan sekali."""
    old = app_dir() / "settings.json"
    new = settings_file()
    if old.exists() and not new.exists():
        try:
            shutil.copy2(old, new)
        except OSError:
            pass


def work_dir(image_path: str, custom: str = "", create: bool = True) -> Path:
    """Folder kerja (hasil render & gambar bersih) untuk satu chapter.
    Bawaan: tersembunyi di folder data aplikasi, jadi folder chapter tetap bersih —
    gambar baru keluar ke folder pilihan saat Export. Bila 'Folder hasil kerja' diisi, pakai itu."""
    if custom:
        d = Path(custom)
    else:
        import hashlib
        src = Path(image_path).resolve().parent
        h = hashlib.sha1(str(src).lower().encode("utf-8")).hexdigest()[:10]
        name = "".join(c for c in src.name if c.isalnum() or c in " ._-()").strip()[:60] or "chapter"
        d = data_dir() / "work" / f"{name}-{h}"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d
