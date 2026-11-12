"""Export As: pilih halaman (saat ini / semua / rentang) lalu simpan sebagai
PDF (manga / manhwa / manhua), CBZ + ComicInfo.xml (dibaca Mihon, Komga, Kavita, dll.)
atau ZIP gambar biasa.

Paket "Local Source Mihon" = satu .zip berisi folder seri:
    <Judul Seri>/
        cover.jpg
        ComicInfo.xml       (info seri: judul, penulis, genre, status, ringkasan)
        details.json        (format lama, untuk fork Tachiyomi yang belum membaca ComicInfo seri)
        Ch. 12 - Judul.cbz  (gambar 001.png … + ComicInfo.xml chapter)
Ekstrak isinya ke folder  Mihon/local/  di HP, lalu buka Browse → Local source.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

from .models import Project

KINDS = ("auto", "manga", "manhwa", "manhua")
FORMATS = ("pdf", "cbz", "zip", "psd")
STATUS = {  # teks tampilan -> (nilai ComicInfo Mihon, kode details.json)
    "Tidak diketahui": ("Unknown", "0"),
    "Berlanjut (ongoing)": ("Ongoing", "1"),
    "Tamat (completed)": ("Completed", "2"),
    "Hiatus": ("On hiatus", "6"),
    "Dibatalkan": ("Cancelled", "5"),
}


# ---------------------------------------------------------------- pilih halaman
def parse_range(text: str, n: int) -> list[int]:
    """'1-3, 5, 8-' -> indeks 0-based yang valid, urut & unik. Kosong = semua."""
    text = (text or "").strip()
    if not text:
        return list(range(n))
    out = []
    for part in re.split(r"[,;\s]+", text):
        if not part:
            continue
        m = re.fullmatch(r"(\d*)\s*[-–]\s*(\d*)", part)
        if m:
            a = int(m.group(1)) if m.group(1) else 1
            b = int(m.group(2)) if m.group(2) else n
            if a > b:
                a, b = b, a
            out.extend(range(a, b + 1))
        elif part.isdigit():
            out.append(int(part))
        else:
            raise ValueError(f"Rentang tidak dikenali: '{part}'. Contoh: 1-5, 8, 10-12")
    seen, res = set(), []
    for i in out:
        if 1 <= i <= n and i not in seen:
            seen.add(i)
            res.append(i - 1)
    if not res:
        raise ValueError(f"Rentang di luar halaman yang ada (1–{n}).")
    return sorted(res)


def page_file(page, use_original: bool) -> str:
    if page.output_path and Path(page.output_path).exists():
        return page.output_path
    if use_original and Path(page.path).exists():
        return page.path
    return ""


def collect(project: Project, indices: list[int], use_original: bool) -> list[str]:
    files = [page_file(project.pages[i], use_original) for i in indices if 0 <= i < len(project.pages)]
    return [f for f in files if f]


def image_size(f: str) -> tuple[int, int]:
    try:
        with Image.open(f) as im:
            return im.size
    except Exception:
        return (0, 0)


def detect_kind(files: list[str]) -> str:
    from .pdfexport import detect_kind as dk
    return "manhwa" if dk(files) == "webtoon" else "manga"


def estimate_pdf_pages(files: list[str], kind: str) -> int:
    if kind == "manga":
        return len(files)
    from .pdfexport import PDF_MAX
    sizes = [image_size(f) for f in files]
    sizes = [s for s in sizes if s[0]]
    if not sizes:
        return 0
    ws = sorted(w for w, _ in sizes)
    W = min(ws[len(ws) // 2], PDF_MAX)
    total = sum(h * W / w for w, h in sizes)
    return max(1, -(-int(total) // PDF_MAX))


def guess_chapter(project: Project) -> str:
    if not project.pages:
        return ""
    name = Path(project.pages[0].path).parent.name
    m = re.search(r"(?:ch(?:apter)?|ep(?:isode)?|bab)\.?\s*(\d+(?:\.\d+)?)", name, re.I) or \
        re.search(r"(\d+(?:\.\d+)?)\s*$", name)
    return m.group(1) if m else ""


def safe_name(s: str, fallback: str = "Rexxa") -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s or "").strip().rstrip(".")
    return s[:120] or fallback


# ---------------------------------------------------------------- gambar
def _to_rgb(im: Image.Image) -> Image.Image:
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        return bg
    return im.convert("RGB")


def encode(f: str, fmt: str, quality: int) -> tuple[bytes, str]:
    """fmt: asli | jpg | webp -> (data, ekstensi)."""
    ext = Path(f).suffix.lower().lstrip(".") or "png"
    if fmt == "asli":
        return Path(f).read_bytes(), ("jpg" if ext == "jpeg" else ext)
    with Image.open(f) as im:
        im = _to_rgb(im)
        buf = io.BytesIO()
        if fmt == "webp":
            im.save(buf, "WEBP", quality=quality, method=4)
            return buf.getvalue(), "webp"
        im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
        return buf.getvalue(), "jpg"


# ---------------------------------------------------------------- ComicInfo
def _el(tag, val):
    val = "" if val is None else str(val).strip()
    return f"  <{tag}>{escape(val)}</{tag}>\n" if val else ""


def comicinfo_chapter(meta: dict, kind: str, sizes: list[tuple[int, int]], lang: str) -> str:
    num = meta.get("chapter", "")
    title = meta.get("chapter_title", "") or (f"Chapter {num}" if num else "")
    tags = {"manga": "Manga", "manhwa": "Manhwa", "manhua": "Manhua"}.get(kind, "")
    x = '<?xml version="1.0" encoding="utf-8"?>\n'
    x += ('<ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
          'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n')
    x += _el("Title", title) + _el("Series", meta.get("series")) + _el("Number", num)
    x += _el("Volume", meta.get("volume"))
    x += _el("Summary", meta.get("summary")) + _el("Writer", meta.get("author"))
    x += _el("Penciller", meta.get("artist")) + _el("Translator", meta.get("translator"))
    x += _el("Genre", meta.get("genre")) + _el("Tags", tags) + _el("LanguageISO", lang)
    x += _el("Web", meta.get("web"))
    x += _el("PageCount", len(sizes))
    x += _el("Manga", "YesAndRightToLeft" if kind == "manga" else "No")
    x += _el("Notes", "Dibuat dengan Rexxa Translator")
    x += "  <Pages>\n"
    for i, (w, h) in enumerate(sizes):
        t = ' Type="FrontCover"' if i == 0 else ""
        dims = f' ImageWidth="{w}" ImageHeight="{h}"' if w else ""
        x += f'    <Page Image="{i}"{t}{dims} />\n'
    x += "  </Pages>\n</ComicInfo>\n"
    return x


def comicinfo_series(meta: dict, kind: str) -> str:
    status = STATUS.get(meta.get("status", ""), STATUS["Tidak diketahui"])[0]
    x = '<?xml version="1.0" encoding="utf-8"?>\n'
    x += ('<ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
          'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
          'xmlns:ty="http://www.w3.org/2001/XMLSchema">\n')
    x += _el("Series", meta.get("series")) + _el("Summary", meta.get("summary"))
    x += _el("Writer", meta.get("author")) + _el("Penciller", meta.get("artist"))
    x += _el("Genre", meta.get("genre"))
    x += _el("Manga", "YesAndRightToLeft" if kind == "manga" else "No")
    x += f"  <ty:PublishingStatusTachiyomi>{escape(status)}</ty:PublishingStatusTachiyomi>\n"
    x += "</ComicInfo>\n"
    return x


def details_json(meta: dict) -> str:
    genres = [g.strip() for g in re.split(r"[,;]", meta.get("genre", "") or "") if g.strip()]
    return json.dumps({
        "title": meta.get("series", ""),
        "author": meta.get("author", ""),
        "artist": meta.get("artist", "") or meta.get("author", ""),
        "description": meta.get("summary", ""),
        "genre": genres,
        "status": STATUS.get(meta.get("status", ""), STATUS["Tidak diketahui"])[1],
    }, ensure_ascii=False, indent=2)


def chapter_filename(meta: dict) -> str:
    num, title = (meta.get("chapter") or "").strip(), (meta.get("chapter_title") or "").strip()
    name = (f"Ch. {num}" if num else "Chapter") + (f" - {title}" if title else "")
    return safe_name(name, "Chapter")


# ---------------------------------------------------------------- tulis
def _cbz_bytes(files, meta, kind, lang, img_fmt, quality, log=None, stop=None) -> tuple[bytes, list]:
    buf = io.BytesIO()
    pad = max(3, len(str(len(files))))
    sizes = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for i, f in enumerate(files, 1):
            if stop and stop():
                raise RuntimeError("Dibatalkan.")
            data, ext = encode(f, img_fmt, quality)
            z.writestr(f"{i:0{pad}d}.{ext}", data)
            sizes.append(image_size(f))
            if log:
                log(i, len(files))
        z.writestr("ComicInfo.xml", comicinfo_chapter(meta, kind, sizes, lang))
    return buf.getvalue(), sizes


def export_psd(project: Project, out_path: str, indices: list[int], settings: dict, progress=None, stop=None,
               log=None) -> dict:
    """Satu .psd per halaman (lapisan: Raw, Bersih, tiap balon teks). Lebih dari satu halaman -> .zip."""
    import tempfile
    from . import detector, pipeline, psd
    done = []
    tmp = Path(tempfile.mkdtemp(prefix="rexxa_psd_"))
    pad = max(3, len(str(len(project.pages))))
    for k, i in enumerate(indices, 1):
        if stop and stop():
            raise RuntimeError("Dibatalkan.")
        p = project.pages[i]
        try:
            clean, final, layers = pipeline.render_layers(p, project, settings)
        except ValueError as e:
            if log:
                log(str(e))
            continue
        tl = []
        for b, im, x, y in layers:
            n = p.blocks.index(b) + 1 if b in p.blocks else 0
            txt = " ".join((b.translation or project.series_title or "").split())
            label = "Judul seri" if b.kind == "title" else f"Gambar {n}" if b.kind == "image" else f"Teks {n}"
            tl.append((f"{label}: {txt[:40]}", im, x, y))
        name = f"{i + 1:0{pad}d}_{safe_name(Path(p.path).stem, 'halaman')}.psd"
        f = tmp / name
        try:
            raw = detector.load_image(p.path)
        except Exception:
            raw = None
        psd.page_psd(str(f), raw, clean, final, tl)
        done.append(f)
        if progress:
            progress(k, len(indices))
    if not done:
        raise ValueError("Tidak ada halaman yang sudah dirender untuk dijadikan PSD.")
    if len(done) == 1 and out_path.lower().endswith(".psd"):
        Path(out_path).write_bytes(done[0].read_bytes())
    else:
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
            for f in done:
                z.write(f, f.name)
    for f in done:
        try:
            f.unlink()
        except OSError:
            pass
    return {"files": len(done), "kind": "manga", "out": out_path, "pages_out": len(done)}


def export(project: Project, out_path: str, *, fmt: str, kind: str, indices: list[int],
           use_original: bool = False, img_fmt: str = "asli", quality: int = 90,
           meta: dict | None = None, mihon_pack: bool = False, progress=None, stop=None,
           settings: dict | None = None, credit_page: bool = False, watermark: bool = False, log=None) -> dict:
    """Mengembalikan ringkasan {"files", "kind", "out", "pages_out"}."""
    from . import detector
    detector.flush_writes()                 # hasil edit terakhir sudah tertulis ke disk
    meta = dict(meta or {})
    meta.setdefault("series", project.series_title)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    if fmt == "img":
        Path(out_path).mkdir(parents=True, exist_ok=True)
    if fmt == "psd":
        return export_psd(project, out_path, indices, settings or {}, progress, stop, log)
    files = collect(project, indices, use_original)
    if not files:
        raise ValueError("Tidak ada halaman yang bisa diekspor (belum diterjemahkan).")
    if kind == "auto":
        kind = detect_kind(files)
    lang = project.target_lang
    cover_src = files[0]
    if credit_page or watermark:
        import tempfile
        from . import skills
        cfg = skills.credits_cfg(settings or {})
        cfg["page"], cfg["watermark"] = bool(credit_page), bool(watermark)
        files = skills.apply_credits(files, cfg, meta, tempfile.mkdtemp(prefix="rexxa_credit_"),
                                     "manga" if kind == "manga" else "webtoon")

    if fmt == "pdf":
        from . import pdfexport
        r = pdfexport.export_files(files, out_path, "manga" if kind == "manga" else "webtoon",
                                   quality=quality, jpeg=(img_fmt != "asli"), title=meta.get("series", ""))
        return {"files": len(files), "kind": kind, "out": out_path, "pages_out": r["pages_out"]}

    if fmt == "img":                    # gambar lepas ke folder pilihan
        pad = max(3, len(str(len(files))))
        for i, f in enumerate(files, 1):
            if stop and stop():
                raise RuntimeError("Dibatalkan.")
            data, ext = encode(f, img_fmt, quality)
            (Path(out_path) / f"{i:0{pad}d}.{ext}").write_bytes(data)
            if progress:
                progress(i, len(files))
        return {"files": len(files), "kind": kind, "out": out_path, "pages_out": len(files)}

    if fmt == "zip":
        pad = max(3, len(str(len(files))))
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_STORED) as z:
            for i, f in enumerate(files, 1):
                if stop and stop():
                    raise RuntimeError("Dibatalkan.")
                data, ext = encode(f, img_fmt, quality)
                z.writestr(f"{i:0{pad}d}.{ext}", data)
                if progress:
                    progress(i, len(files))
        return {"files": len(files), "kind": kind, "out": out_path, "pages_out": len(files)}

    # cbz
    data, _ = _cbz_bytes(files, meta, kind, lang, img_fmt, quality, progress, stop)
    if not mihon_pack:
        Path(out_path).write_bytes(data)
        return {"files": len(files), "kind": kind, "out": out_path, "pages_out": len(files)}
    series = safe_name(meta.get("series", ""), "Rexxa Translator")
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_STORED) as z:
        z.writestr(f"{series}/{chapter_filename(meta)}.cbz", data)
        z.writestr(f"{series}/ComicInfo.xml", comicinfo_series(meta, kind))
        z.writestr(f"{series}/details.json", details_json(meta))
        with Image.open(cover_src) as im:
            im = _to_rgb(im)
            if im.height > im.width * 1.6:          # strip webtoon: ambil potongan atas saja
                im = im.crop((0, 0, im.width, int(im.width * 1.45)))
            im.thumbnail((720, 1080))
            b = io.BytesIO()
            im.save(b, "JPEG", quality=88)
        z.writestr(f"{series}/cover.jpg", b.getvalue())
    return {"files": len(files), "kind": kind, "out": out_path, "pages_out": len(files), "series": series}
