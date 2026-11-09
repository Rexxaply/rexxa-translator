"""Unduh & pasang update.

Update KODE  : zip berisi folder app/  -> diekstrak ke app.new/, lalu app/ -> app.old/, app.new/ -> app/.
               File .py tidak dikunci Windows, jadi bisa dilakukan saat aplikasi berjalan; tinggal restart.
               Kalau versi baru gagal dibuka, main.py otomatis kembali ke app.old/.
Update PENUH : zip berisi folder RexxaTranslator/ (mesin + kode). File .exe & DLL sedang dipakai,
               jadi penyalinan dilakukan skrip kecil yang menunggu aplikasi tertutup, menyalin,
               lalu membuka aplikasi lagi.
Data pengguna (pengaturan, API key, font) ada di %APPDATA% dan tidak tersentuh.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

from . import paths

EXE_NAME = "RexxaTranslator.exe"


class UpdateError(Exception):
    pass


def base_dir() -> Path:
    return Path(os.environ.get("REXXA_BASE") or paths.app_dir())


def downloads_dir() -> Path:
    d = paths.data_dir() / "updates"
    d.mkdir(exist_ok=True)
    return d


def download(asset: dict, progress=None, cancelled=lambda: False) -> Path:
    url = asset["url"]
    dest = downloads_dir() / url.rsplit("/", 1)[-1].split("?")[0]
    h = hashlib.sha256()
    done = 0
    with requests.get(url, stream=True, timeout=30, headers={"User-Agent": "RexxaTranslator-updater"}) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or asset.get("size") or 0)
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                if cancelled():
                    f.close()
                    tmp.unlink(missing_ok=True)
                    raise UpdateError("Unduhan dibatalkan.")
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    want = (asset.get("sha256") or "").lower()
    if want and h.hexdigest() != want:
        tmp.unlink(missing_ok=True)
        raise UpdateError("File unduhan rusak (checksum tidak cocok). Coba lagi.")
    tmp.replace(dest)
    return dest


def _safe_extract(zf: zipfile.ZipFile, target: Path):
    target = target.resolve()
    for m in zf.infolist():
        p = (target / m.filename).resolve()
        if not str(p).startswith(str(target)):
            raise UpdateError(f"Isi zip tidak aman: {m.filename}")
    zf.extractall(target)


def install_app_update(zip_path: Path, base: Path | None = None) -> Path:
    """Pasang update kode. Mengembalikan folder kode yang baru."""
    base = base or base_dir()
    staging = Path(tempfile.mkdtemp(prefix="rexxa-app-", dir=downloads_dir()))
    try:
        with zipfile.ZipFile(zip_path) as z:
            _safe_extract(z, staging)
        new_code = staging / "app"
        if not (new_code / "core" / "version.py").exists() or not (new_code / "gui").is_dir():
            raise UpdateError("Paket update tidak lengkap (folder app/core tidak ada).")

        if paths.is_frozen() or (base / "app").is_dir():
            app, new, old = base / "app", base / "app.new", base / "app.old"
            shutil.rmtree(new, ignore_errors=True)
            shutil.move(str(new_code), str(new))
            shutil.rmtree(old, ignore_errors=True)
            if app.exists():
                os.replace(app, old)
            os.replace(new, app)
            return app
        # dijalankan dari source (core/ & gui/ langsung di root): timpa file
        for item in new_code.iterdir():
            dst = base / item.name
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)
        return base
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def prepare_full_update(zip_path: Path, base: Path | None = None) -> Path:
    """Ekstrak update penuh & tulis skrip pemasang. Jalankan skripnya lalu tutup aplikasi."""
    base = base or base_dir()
    staging = Path(tempfile.mkdtemp(prefix="rexxa-full-", dir=downloads_dir()))
    with zipfile.ZipFile(zip_path) as z:
        _safe_extract(z, staging)
    src = next((p.parent for p in staging.rglob(EXE_NAME)), None)
    if src is None:
        shutil.rmtree(staging, ignore_errors=True)
        raise UpdateError(f"{EXE_NAME} tidak ditemukan di paket update.")
    log = downloads_dir() / "update-log.txt"
    bat = downloads_dir() / "pasang-update.bat"
    bat.write_text("\r\n".join([
        "@echo off",
        "title Memasang update Rexxa Translator",
        "echo Menunggu Rexxa Translator tertutup...",
        f"set PID={os.getpid()}",
        ":wait",
        'tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul && (timeout /t 1 /nobreak >nul & goto wait)',
        "echo Menyalin file baru...",
        f'robocopy "{src}" "{base}" /E /R:5 /W:1 /NFL /NDL /NP > "{log}"',
        "if %ERRORLEVEL% GEQ 8 (echo GAGAL menyalin - lihat " + str(log) + " & pause & exit /b 1)",
        f'rmdir /s /q "{base / "app.old"}" 2>nul',
        f'start "" "{base / EXE_NAME}"',
        f'rmdir /s /q "{staging}" 2>nul',
        f'del "{zip_path}" 2>nul',
        "exit",
    ]) + "\r\n", encoding="utf-8")
    return bat


def run_detached(bat: Path):
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(["cmd", "/c", str(bat)], creationflags=flags, close_fds=True)


def restart_command() -> list[str]:
    if paths.is_frozen():
        return [sys.executable] + sys.argv[1:]
    return [sys.executable, str(base_dir() / "main.py")] + sys.argv[1:]
