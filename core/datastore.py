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
                d = paths.work_dir(pg.path, (settings or {}).get("output_dir") or "", create=False) / ".cache"
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


# ---------------------------------------------------------------- folder kerja per chapter

def work_root() -> Path:
    return paths.data_dir() / "work"


def _last_used(d: Path) -> float:
    for f in (d / ".used", d):
        try:
            return f.stat().st_mtime
        except OSError:
            pass
    return 0.0


def work_dirs() -> list[dict]:
    """Folder kerja tiap chapter: {path, name, source, bytes, files, used} — terbaru dulu."""
    out = []
    root = work_root()
    if not root.exists():
        return out
    for d in root.iterdir():
        if not d.is_dir():
            continue
        try:
            src = (d / ".source").read_text(encoding="utf-8").strip()
        except OSError:
            src = ""
        b, c = size_of(d)
        name = Path(src).name if src else d.name.rsplit("-", 1)[0]
        parent = Path(src).parent.name if src else ""
        out.append({"path": d, "name": name, "series": parent, "source": src, "bytes": b, "files": c,
                    "used": _last_used(d)})
    out.sort(key=lambda x: -x["used"])
    return out


def project_work_dirs(project, settings: dict | None = None) -> set:
    """Folder kerja proyek yang sedang terbuka (tidak boleh dihapus otomatis)."""
    out = set()
    if project is None or (settings or {}).get("output_dir"):
        return out
    for pg in project.pages:
        try:
            out.add(paths.work_dir(pg.path, create=False).resolve())
        except Exception:
            pass
    return out


def touch_project(project, settings: dict | None = None):
    for d in project_work_dirs(project, settings):
        if d.exists():
            paths.touch_work(d)


def delete_work(dirs) -> list[str]:
    from . import detector
    detector.flush_writes(15)
    failed = []
    for d in dirs:
        failed += remove(Path(d))
    return failed


def auto_cleanup(days: int, protect=()) -> tuple[int, int]:
    """Hapus folder kerja yang tidak dipakai lebih dari `days` hari. -> (jumlah folder, byte dibebaskan)."""
    import time
    if not days or days <= 0:
        return 0, 0
    limit = time.time() - days * 86400
    keep = {Path(p).resolve() for p in protect}
    n = freed = 0
    for w in work_dirs():
        if w["used"] and w["used"] < limit and Path(w["path"]).resolve() not in keep:
            if not remove(w["path"]):
                n += 1
                freed += w["bytes"]
    return n, freed
