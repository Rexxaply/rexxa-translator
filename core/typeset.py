"""Typesetting: menulis teks terjemahan ke dalam balon dengan ukuran otomatis."""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .models import TextBlock
from .paths import app_dir, bundled_fonts_dir, user_fonts_dir  # noqa: F401  (app_dir dipakai modul lain)


def fonts_dir() -> Path:
    """Folder tempat user menaruh font sendiri (aman dari update)."""
    return user_fonts_dir()


FALLBACK_FONTS = [
    # Windows
    "C:/Windows/Fonts/comicbd.ttf", "C:/Windows/Fonts/comic.ttf",
    "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
CJK_FONTS = [
    "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/malgun.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
]


# Font gaya lettering komik, urut dari yang paling mirip scanlation profesional.
# Nama file dicocokkan tanpa huruf besar/kecil, spasi, '-' dan '_'.
COMIC_PREF = [
    "ccwildwords", "wildwordsroman", "wildwords",       # Wild Words (Comicraft) — standar scanlation
    "animeace", "animeace2",                            # Anime Ace (Blambot)
    "comicneuebolditalic", "comicneuebold",             # Comic Neue (OFL) — ikut dibundel
    "comicbd",                                          # Comic Sans MS Bold (bawaan Windows)
]
SYSTEM_FONT_DIRS = [Path("C:/Windows/Fonts"),
                    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"]
FONT_EXT = (".ttf", ".otf", ".ttc")


def _key(p) -> str:
    return "".join(ch for ch in Path(p).stem.lower() if ch.isalnum())


def _comic_rank(p) -> int:
    k = _key(p)
    for i, pat in enumerate(COMIC_PREF):
        if k.startswith(pat):
            return i
    return len(COMIC_PREF)


def list_fonts() -> list[str]:
    """Font milik user + font bawaan aplikasi + font komik yang terpasang di Windows + cadangan."""
    found = []
    for d in (user_fonts_dir(), bundled_fonts_dir()):
        if d.exists():
            found += sorted(str(p) for p in d.glob("*") if p.suffix.lower() in FONT_EXT)
    for d in SYSTEM_FONT_DIRS:
        if str(d) not in (".", "") and d.exists():
            try:
                found += sorted(str(p) for p in d.iterdir()
                                if p.suffix.lower() in FONT_EXT and _comic_rank(p) < len(COMIC_PREF))
            except OSError:
                pass
    for f in FALLBACK_FONTS + CJK_FONTS:
        if os.path.exists(f):
            found.append(f)
    out, seen = [], set()
    for f in found:
        if f.lower() not in seen:
            seen.add(f.lower())
            out.append(f)
    return out


def default_font(target_lang: str) -> str:
    if target_lang in ("ja", "zh", "zh-tw", "ko"):
        for f in CJK_FONTS:
            if os.path.exists(f):
                return f
    fonts = list_fonts()
    comic = sorted((f for f in fonts if _comic_rank(f) < len(COMIC_PREF)), key=_comic_rank)
    return (comic or fonts or [""])[0]


def is_italic_font(path: str) -> bool:
    """Font yang bentuknya sudah miring (tidak perlu dimiringkan lagi)."""
    k = _key(path)
    return "italic" in k or "oblique" in k or k.startswith(("ccwildwords", "wildwords"))


def italic_variant(path: str) -> str | None:
    """Cari file versi miring dari font yang sama (mis. ComicNeue-Bold -> ComicNeue-BoldItalic)."""
    p = Path(path)
    if not path or not p.exists():
        return None
    stem = p.stem
    cands = [stem + "Italic", stem + "-Italic", stem.replace("Regular", "Italic"),
             stem.replace("-Bold", "-BoldItalic"), stem.replace("Bold", "BoldItalic")]
    for c in cands:
        if c != stem:
            for ext in FONT_EXT:
                q = p.with_name(c + ext)
                if q.exists():
                    return str(q)
    return None


# ---------------------------------------------------------------- instal font milik pengguna

class FontError(Exception):
    pass


def font_name(path: str) -> str:
    """Nama tampilan font, mis. 'Wild Words Roman' / 'Comic Neue Bold Italic'."""
    try:
        fam, style = ImageFont.truetype(path, 20).getname()
        style = "" if (style or "").lower() in ("regular", "normal", "roman", "") else f" {style}"
        return f"{fam}{style}"
    except Exception:
        return Path(path).stem


def user_fonts() -> list[str]:
    d = user_fonts_dir()
    return sorted((str(p) for p in d.iterdir() if p.suffix.lower() in FONT_EXT), key=lambda p: font_name(p).lower())


def install_font(src: str) -> str:
    """Salin file font ke folder font pengguna (%APPDATA%\\RexxaTranslator\\fonts).
    Font di sana tetap ada walau aplikasi di-update. Mengembalikan path tujuan."""
    import shutil
    sp = Path(src)
    if sp.suffix.lower() not in FONT_EXT:
        raise FontError(f"{sp.name}: bukan file font (.ttf / .otf / .ttc).")
    try:
        ImageFont.truetype(str(sp), 20)
    except Exception:
        raise FontError(f"{sp.name}: file font rusak atau tidak didukung.")
    d = user_fonts_dir()
    dst = d / sp.name
    if dst.exists():
        if dst.stat().st_size == sp.stat().st_size:
            return str(dst)                      # sudah terpasang
        n = 2
        while (d / f"{sp.stem}-{n}{sp.suffix}").exists():
            n += 1
        dst = d / f"{sp.stem}-{n}{sp.suffix}"
    shutil.copy2(sp, dst)
    _font.cache_clear()
    return str(dst)


def remove_font(path: str):
    p = Path(path).resolve()
    if p.parent != user_fonts_dir().resolve():
        raise FontError("Hanya font yang diinstal lewat aplikasi yang bisa dihapus di sini.")
    p.unlink(missing_ok=True)
    _font.cache_clear()


def windows_comic_fonts() -> list[str]:
    """Font komik (Wild Words, Anime Ace, …) yang terpasang di Windows."""
    out = []
    for d in SYSTEM_FONT_DIRS:
        if str(d) not in (".", "") and d.exists():
            try:
                out += [str(p) for p in d.iterdir() if p.suffix.lower() in FONT_EXT and _comic_rank(p) < len(COMIC_PREF)]
            except OSError:
                pass
    return out


@lru_cache(maxsize=256)
def _font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size) if path else ImageFont.load_default(size)
    except OSError:
        return ImageFont.load_default(size)


def _text_w(draw, text, font, stroke=0):
    if not text:
        return 0
    l, t, r, b = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    return r - l


def wrap_text(draw, text: str, font, max_w: int, stroke: int = 0, allow_break: bool = True):
    """Bungkus per kata; kata kepanjangan dipotong dengan tanda hubung.
    Untuk teks tanpa spasi (CJK) bungkus per karakter."""
    lines: list[str] = []
    for para in text.split("\n"):
        if " " not in para.strip() and len(para) > 1 and any(ord(c) > 0x2E80 for c in para):
            cur = ""
            for ch in para:
                if _text_w(draw, cur + ch, font, stroke) <= max_w or not cur:
                    cur += ch
                else:
                    lines.append(cur)
                    cur = ch
            lines.append(cur)
            continue
        cur = ""
        for word in _split_hyphens(para.split()):
            joiner = "" if cur.endswith("-") and getattr(word, "after_hyphen", False) else " "
            trial = (cur + joiner + word).strip()
            if _text_w(draw, trial, font, stroke) <= max_w:
                cur = trial
                continue
            if cur:
                lines.append(cur)
                cur = ""
            # kata terlalu panjang untuk satu baris -> pecah (hanya kalau diizinkan)
            if not allow_break and _text_w(draw, word, font, stroke) > max_w:
                return None
            while _text_w(draw, word, font, stroke) > max_w and sum(c.isalnum() for c in word) > 5:
                cut = len(word) - 1
                while cut > 3 and _text_w(draw, word[:cut] + "-", font, stroke) > max_w:
                    cut -= 1
                lines.append(word[:cut] + "-")
                word = word[cut:]
            cur = word
        lines.append(cur)
    return [l for l in lines if l is not None]


class _Piece(str):
    """Bagian kata setelah tanda hubung (digabung tanpa spasi bila satu baris)."""
    after_hyphen = True


def _split_hyphens(words):
    out = []
    for w in words:
        parts = re.split(r"(?<=[^\W\d_]-)(?=\w)", w)   # pisah di "KATSUKI-|SAN!", bukan di "-" awal/angka
        out.append(parts[0])
        out += [_Piece(p) for p in parts[1:]]
    return out


def text_area(b: TextBlock) -> tuple[int, int, int, int]:
    """Area aman di dalam balon (balon oval -> kotak dalam ±70-80%)."""
    if b.kind == "bubble":
        sx, sy = 0.80, 0.72
        w, h = int(b.w * sx), int(b.h * sy)
        return b.x + (b.w - w) // 2, b.y + (b.h - h) // 2, w, h
    return b.x, b.y, b.w, b.h


def fit_text(draw, text, font_path, area_w, area_h, stroke=0, max_size=64, min_size=8, line_spacing=1.12):
    """Cari ukuran font terbesar yang muat. Utamakan TANPA memotong kata;
    pemotongan kata (tanda hubung) hanya dipakai kalau terpaksa."""
    def search(allow_break):
        lo, hi, best = min_size, max_size, None
        while lo <= hi:
            mid = (lo + hi) // 2
            f = _font(font_path, mid)
            lines = wrap_text(draw, text, f, area_w, stroke, allow_break)
            ok = lines is not None
            if ok:
                total_h = int(mid * line_spacing) * len(lines)
                widest = max((_text_w(draw, l, f, stroke) for l in lines), default=0)
                ok = total_h <= area_h and widest <= area_w
            if ok:
                best = (mid, lines)
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    # Kata TIDAK dipotong (seperti lettering profesional): lebih baik font sedikit lebih kecil.
    # Pemotongan dengan tanda hubung hanya bila satu kata pun tidak muat di ukuran terkecil.
    best = search(False) or search(True)
    if best is None:
        f = _font(font_path, min_size)
        best = (min_size, wrap_text(draw, text, f, area_w, stroke, True))
    return best


def fit_text_ellipse(draw, text, font_path, W, H, stroke=0, max_size=64, min_size=8, line_spacing=1.05):
    """Muatkan teks ke dalam OVAL W x H (bentuk balon kata): baris tengah boleh lebih panjang,
    baris atas/bawah lebih pendek — seperti lettering profesional. Mencoba beberapa lebar
    pembungkus dan memilih ukuran font terbesar yang muat tanpa memotong kata."""
    import math

    def fits(lines, f, lh):
        total = lh * len(lines)
        if total > H:
            return False
        top = -total / 2
        for i, line in enumerate(lines):
            a, b = top + i * lh, top + (i + 1) * lh
            ymax = max(abs(a), abs(b)) - lh * 0.15       # huruf tidak setinggi kotak barisnya
            r = max(0.0, 1 - (2 * max(0.0, ymax) / H) ** 2)
            if _text_w(draw, line, f, stroke) > W * math.sqrt(r):
                return False
        return True

    def try_size(size, allow_break):
        f = _font(font_path, size)
        lh = int(size * line_spacing)
        for frac in (0.95, 0.85, 0.75, 0.65, 0.55):
            lines = wrap_text(draw, text, f, int(W * frac), stroke, allow_break)
            if lines and fits(lines, f, lh):
                return lines
        return None

    for allow_break in (False, True):
        lo, hi, best = min_size, max_size, None
        while lo <= hi:
            mid = (lo + hi) // 2
            lines = try_size(mid, allow_break)
            if lines:
                best = (mid, lines)
                lo = mid + 1
            else:
                hi = mid - 1
        if best:
            return best
    return min_size, wrap_text(draw, text, _font(font_path, min_size), int(W * 0.8), stroke, True)


BUBBLE_MARGIN = 0.10   # jarak teks dari garis balon (per sisi, relatif ukuran balon)
SHEAR = 0.2            # kemiringan italic palsu


def render_page(img_bgr: np.ndarray, blocks: list[TextBlock], target_lang: str = "id",
                default_font_path: str = "", uppercase: bool = True, max_size: int = 64,
                italic: bool = True, line_spacing: float = 1.05) -> np.ndarray:
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)).convert("RGBA")
    measure = ImageDraw.Draw(pil)
    base_font = default_font_path or default_font(target_lang)
    latin = target_lang not in ("ja", "zh", "zh-tw", "ko")

    for b in blocks:
        text = (b.translation or "").strip()
        if not text:
            continue
        if uppercase and latin:
            text = text.upper()
        font_path = b.font or base_font
        want_italic = (b.italic if b.italic is not None else italic) and latin
        shear = 0.0
        if want_italic and not is_italic_font(font_path):
            v = italic_variant(font_path)
            if v:
                font_path = v
            else:
                shear = SHEAR
        stroke = b.stroke_width
        oval = b.kind == "bubble"
        if oval:  # area oval di dalam balon
            mx, my = int(b.w * BUBBLE_MARGIN), int(b.h * BUBBLE_MARGIN)
            ax, ay, aw, ah = b.x + mx, b.y + my, b.w - 2 * mx, b.h - 2 * my
        else:
            ax, ay, aw, ah = text_area(b)
        full_w = aw
        if shear:  # sisakan ruang untuk kemiringan
            aw = max(10, int(aw - ah * shear * (0.25 if oval else 0.5)))
        if b.font_size > 0:
            size = b.font_size
            lines = wrap_text(measure, text, _font(font_path, size), aw, stroke)
        elif oval:
            size, lines = fit_text_ellipse(measure, text, font_path, aw, ah, stroke, max_size=max_size,
                                           line_spacing=line_spacing)
        else:
            size, lines = fit_text(measure, text, font_path, aw, ah, stroke, max_size=max_size,
                                   line_spacing=line_spacing)
        font = _font(font_path, size)
        lh = int(size * line_spacing)
        total_h = lh * len(lines)

        # gambar di lapisan transparan per balon, lalu (bila perlu) dimiringkan
        pad = size
        lw_, lh_ = aw + 2 * pad, ah + 2 * pad
        layer = Image.new("RGBA", (lw_, lh_), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        y = pad + (ah - total_h) // 2
        for line in lines:
            w_line = _text_w(d, line, font, stroke)
            if b.align == "left":
                x = pad
            elif b.align == "right":
                x = pad + aw - w_line
            else:
                x = pad + (aw - w_line) // 2
            d.text((x, y), line, font=font, fill=b.color,
                   stroke_width=stroke, stroke_fill=b.stroke_color if stroke else None)
            if b.bold and not stroke:  # bold palsu untuk font tanpa varian tebal
                d.text((x + max(1, size // 28), y), line, font=font, fill=b.color)
            y += lh
        if shear:
            # x_input = x + k*(y - tengah): bagian atas bergeser ke kanan -> miring ke kanan
            layer = layer.transform(layer.size, Image.AFFINE, (1, shear, -shear * lh_ / 2, 0, 1, 0),
                                    resample=Image.BICUBIC)
        ox = ax - pad + (full_w - aw) // 2
        _paste_clipped(pil, layer, ox, ay - pad)
    return cv2.cvtColor(np.array(pil.convert("RGB")), cv2.COLOR_RGB2BGR)


def _paste_clipped(base: Image.Image, layer: Image.Image, x: int, y: int):
    """Tempel lapisan, dipotong bila keluar dari tepi gambar (kiri/atas/kanan/bawah)."""
    cx, cy = max(0, -x), max(0, -y)
    ex = min(layer.width, base.width - x)
    ey = min(layer.height, base.height - y)
    if ex <= cx or ey <= cy:
        return
    base.alpha_composite(layer.crop((cx, cy, ex, ey)), (x + cx, y + cy))
