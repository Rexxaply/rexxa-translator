"""Export hasil terjemahan ke satu file PDF.

- Manga (halaman pendek): satu gambar = satu halaman PDF, ukuran mengikuti gambarnya.
- Manhwa / manhua (webtoon, strip panjang): semua halaman DISAMBUNG jadi satu strip panjang
  (lebar disamakan), lalu dipotong menjadi halaman PDF setinggi maksimum yang diizinkan PDF.
  Potongan dicari di baris yang polos (celah di antara panel) supaya panel tidak terbelah.
- Mode "auto" menentukan sendiri dari bentuk halaman (tinggi > 2,5x lebar = webtoon).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from .models import Project

PDF_MAX = 14000          # batas tinggi halaman PDF ±14400 pt (200 inci); 1 px = 1 pt


def page_images(project: Project, use_original_if_missing: bool = False) -> list[str]:
    out = []
    for p in project.pages:
        if p.output_path and Path(p.output_path).exists():
            out.append(p.output_path)
        elif use_original_if_missing and Path(p.path).exists():
            out.append(p.path)
    return out


def detect_kind(paths: list[str]) -> str:
    """"webtoon" bila sebagian besar halaman berbentuk strip panjang, selain itu "manga"."""
    ratios = []
    for f in paths:
        try:
            with Image.open(f) as im:
                w, h = im.size
            ratios.append(h / max(1, w))
        except Exception:
            pass
    if not ratios:
        return "manga"
    return "webtoon" if float(np.median(ratios)) > 2.5 else "manga"


def _rgb(f):
    im = Image.open(f)
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        bg.paste(im, mask=im.split()[-1])
        return bg
    return im.convert("RGB")


def _cut_rows(strip: np.ndarray, max_h: int) -> list[int]:
    """Posisi potong strip (indeks baris) sehingga tiap bagian <= max_h, memilih baris yang paling
    'polos' (celah antar panel) di sepertiga bawah setiap jendela."""
    H = strip.shape[0]
    gray = strip.mean(axis=2) if strip.ndim == 3 else strip
    flat = gray.std(axis=1)                       # baris polos = deviasi kecil
    cuts, start = [], 0
    while H - start > max_h:
        lo, hi = start + int(max_h * 0.6), start + max_h
        seg = flat[lo:hi]
        # utamakan baris polos; bila banyak, ambil yang paling bawah (halaman lebih penuh)
        best = np.nonzero(seg <= max(2.0, float(seg.min()) + 0.5))[0]
        cut = lo + int(best[-1] if best.size else int(np.argmin(seg)))
        cuts.append(cut)
        start = cut
    return cuts


def export_pdf(project: Project, pdf_path: str, kind: str = "auto", quality: int = 90,
               width: int = 0, log=None) -> dict:
    """Mengembalikan {"kind", "pages_in", "pages_out"}."""
    paths = page_images(project)
    if not paths:
        raise ValueError("Belum ada halaman yang diterjemahkan.")
    return export_files(paths, pdf_path, kind, quality=quality, width=width, log=log)


def export_files(paths: list[str], pdf_path: str, kind: str = "auto", quality: int = 90,
                 width: int = 0, log=None, title: str = "", jpeg: bool = True) -> dict:
    """PDF dari daftar file gambar (urutan dipertahankan). Gambar RGB disimpan Pillow
    sebagai JPEG di dalam PDF; `quality` mengatur ukuran/ketajamannya."""
    if not paths:
        raise ValueError("Tidak ada gambar untuk PDF.")
    if kind == "auto":
        kind = detect_kind(paths)
    pages = []
    if kind == "manga":
        pages = [_rgb(f) for f in paths]
    else:
        ims = [_rgb(f) for f in paths]
        W = width or int(np.median([im.width for im in ims]))
        W = min(W, PDF_MAX)
        resized = []
        for im in ims:
            if im.width != W:
                im = im.resize((W, max(1, round(im.height * W / im.width))), Image.LANCZOS)
            resized.append(im)
        total = sum(im.height for im in resized)
        if log:
            log(f"PDF webtoon: {len(resized)} halaman disambung ({W} × {total} px)")
        strip = Image.new("RGB", (W, total), (255, 255, 255))
        y = 0
        for im in resized:
            strip.paste(im, (0, y))
            y += im.height
        arr = np.asarray(strip)
        cuts = [0] + _cut_rows(arr, PDF_MAX) + [total]
        pages = [strip.crop((0, a, W, b)) for a, b in zip(cuts, cuts[1:]) if b > a]
    first, rest = pages[0], pages[1:]
    Path(pdf_path).parent.mkdir(parents=True, exist_ok=True)
    first.save(pdf_path, "PDF", save_all=True, append_images=rest, resolution=72.0, quality=quality,
               title=title or Path(pdf_path).stem, creator="Rexxa Translator")
    return {"kind": kind, "pages_in": len(paths), "pages_out": len(pages)}
