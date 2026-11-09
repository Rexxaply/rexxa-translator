"""Typesetting: menulis teks terjemahan ke dalam balon dengan ukuran otomatis."""
from __future__ import annotations

import os
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


def list_fonts() -> list[str]:
    """Font di folder fonts/ aplikasi + font sistem yang umum dipakai scanlation."""
    found = []
    for d in (user_fonts_dir(), bundled_fonts_dir()):
        if d.exists():
            found += sorted(str(p) for p in d.glob("*") if p.suffix.lower() in (".ttf", ".otf", ".ttc"))
    for f in FALLBACK_FONTS + CJK_FONTS:
        if os.path.exists(f) and f not in found:
            found.append(f)
    win = Path("C:/Windows/Fonts")
    if win.exists():
        for name in ("animeace2_reg.ttf", "wildwordsroman.ttf", "CCWildWords-Regular.ttf",
                     "segoeuib.ttf", "tahomabd.ttf", "verdanab.ttf", "impact.ttf"):
            p = win / name
            if p.exists() and str(p) not in found:
                found.append(str(p))
    return found


def default_font(target_lang: str) -> str:
    pool = (CJK_FONTS if target_lang in ("ja", "zh", "zh-tw", "ko") else []) + list_fonts()
    for f in pool:
        if os.path.exists(f):
            return f
    return ""


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
        for word in para.split():
            trial = (cur + " " + word).strip()
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

    best = search(False)
    # kalau tanpa potong kata fontnya jadi terlalu kecil, izinkan potong kata
    if best is None or best[0] < max(min_size + 2, int(area_h * 0.12)):
        alt = search(True)
        if alt and (best is None or alt[0] > best[0] * 1.35):
            best = alt
    if best is None:
        f = _font(font_path, min_size)
        best = (min_size, wrap_text(draw, text, f, area_w, stroke, True))
    return best


def render_page(img_bgr: np.ndarray, blocks: list[TextBlock], target_lang: str = "id",
                default_font_path: str = "", uppercase: bool = False, max_size: int = 64) -> np.ndarray:
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    base_font = default_font_path or default_font(target_lang)

    for b in blocks:
        text = (b.translation or "").strip()
        if not text:
            continue
        if uppercase:
            text = text.upper()
        font_path = b.font or base_font
        ax, ay, aw, ah = text_area(b)
        stroke = b.stroke_width
        if b.font_size > 0:
            size = b.font_size
            lines = wrap_text(draw, text, _font(font_path, size), aw, stroke)
        else:
            size, lines = fit_text(draw, text, font_path, aw, ah, stroke, max_size=max_size)
        font = _font(font_path, size)
        lh = int(size * 1.12)
        total_h = lh * len(lines)
        y = ay + (ah - total_h) // 2
        for line in lines:
            lw = _text_w(draw, line, font, stroke)
            if b.align == "left":
                x = ax
            elif b.align == "right":
                x = ax + aw - lw
            else:
                x = ax + (aw - lw) // 2
            draw.text((x, y), line, font=font, fill=b.color,
                      stroke_width=stroke, stroke_fill=b.stroke_color if stroke else None)
            if b.bold and not stroke:  # bold palsu untuk font tanpa varian tebal
                draw.text((x + 1, y), line, font=font, fill=b.color)
            y += lh
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
