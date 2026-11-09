"""Data yang disimpan aplikasi: ukuran & penghapusan (dipakai tab Pengaturan → Data)."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import paths


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def size_of(p: Path) -> tuple[int, int]:
    """(byte, jumlah file) untuk file atau folder."""
    p = Path(p)
    if p.is_file():
        return p.stat().st_size, 1
    total = count = 0
    if p.is_dir():
        for root, _dirs, files in os.walk(p):
            for f in files:
                try:
                    total += (Path(root) / f).stat().st_size
                    count += 1
                except OSError:
                    pass
    return total, count


def remove(p: Path) -> list[str]:
    """Hapus file/folder; kembalikan daftar yang gagal dihapus (mis. sedang dipakai)."""
    p = Path(p)
    failed = []
    if p.is_file():
        try:
            p.unlink()
        except OSError:
            failed.append(str(p))
    elif p.is_dir():
        shutil.rmtree(p, onerror=lambda f, path, e: failed.append(path))
    return failed


# ---------------------------------------------------------------- cache gambar & data proses

def cache_paths(project=None, settings: dict | None = None) -> list[Path]:
    """Gambar bersih sementara (.cache) proyek yang terbuka, unduhan update, dan log."""
    out = []
    if project is not None and project.pages:
        seen = set()
        for pg in project.pages:
            try:
                d = Path(settings.get("output_dir") or (Path(pg.path).parent / "translated")) / ".cache"
            except Exception:
                continue
            if d not in seen and d.exists():
                seen.add(d)
                out.append(d)
    dd = paths.data_dir()
    for name in ("updates", "rexxa.log", "rexxa.log.old"):
        p = dd / name
        if p.exists():
            out.append(p)
    return out


def clear_cache(project=None, settings: dict | None = None) -> list[str]:
    failed = []
    for p in cache_paths(project, settings):
        failed += remove(p)
    if project is not None:
        for pg in project.pages:      # gambar bersih akan dibuat ulang saat render berikutnya
            if pg.cleaned_path and not Path(pg.cleaned_path).exists():
                pg.cleaned_path = ""
    return failed


# ---------------------------------------------------------------- model AI yang diunduh

def _home() -> Path:
    return Path(os.path.expanduser("~"))


def model_paths() -> list[tuple[str, Path]]:
    """Model AI yang diunduh otomatis saat pertama dipakai: (nama, lokasi)."""
    hf = Path(os.environ.get("HF_HUB_CACHE") or os.environ.get("HUGGINGFACE_HUB_CACHE")
              or Path(os.environ.get("HF_HOME") or _home() / ".cache" / "huggingface") / "hub")
    torch_home = Path(os.environ.get("TORCH_HOME") or _home() / ".cache" / "torch")
    easy = Path(os.environ.get("EASYOCR_MODULE_PATH") or _home() / ".EasyOCR")
    out = []
    if hf.exists():
        for d in sorted(hf.glob("models--*manga-ocr*")):
            out.append(("manga-ocr (OCR Jepang)", d))
    if (easy / "model").exists():
        out.append(("EasyOCR (OCR Korea/Mandarin/Inggris)", easy / "model"))
    ck = torch_home / "hub" / "checkpoints"
    if ck.exists():
        for f in sorted(ck.glob("*lama*")):
            out.append(("LaMa (hapus teks AI)", f))
    return out


def clear_models() -> list[str]:
    failed = []
    for _name, p in model_paths():
        failed += remove(p)
    return failed


# ---------------------------------------------------------------- reset aplikasi

def factory_reset() -> list[str]:
    """Kembalikan ke pengaturan awal: hapus pengaturan (termasuk API key), cache terjemahan,
    shortcut, unduhan update, dan log. Font yang diinstal & model AI TIDAK dihapus."""
    dd = paths.data_dir()
    failed = []
    for name in ("settings.json", "translation_cache.json", "updates", "rexxa.log", "rexxa.log.old"):
        p = dd / name
        if p.exists():
            failed += remove(p)
    from . import translator
    translator.clear_cache()
    return failed
