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


def _text_w(draw, text, font, stroke=0, ls=0.0):
    if not text:
        return 0
    l, t, r, b = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    return r - l + ls * max(0, len(text) - 1)


def wrap_text(draw, text: str, font, max_w: int, stroke: int = 0, allow_break: bool = True, ls: float = 0.0):
    """Bungkus per kata; kata kepanjangan dipotong dengan tanda hubung.
    Untuk teks tanpa spasi (CJK) bungkus per karakter."""
    lines: list[str] = []
    for para in text.split("\n"):
        if " " not in para.strip() and len(para) > 1 and any(ord(c) > 0x2E80 for c in para):
            cur = ""
            for ch in para:
                if _text_w(draw, cur + ch, font, stroke, ls) <= max_w or not cur:
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
            if _text_w(draw, trial, font, stroke, ls) <= max_w:
                cur = trial
                continue
            if cur:
                lines.append(cur)
                cur = ""
            # kata terlalu panjang untuk satu baris -> pecah (hanya kalau diizinkan)
            if not allow_break and _text_w(draw, word, font, stroke, ls) > max_w:
                return None
            # penggalan buatan hanya untuk kata panjang (>= 9 huruf), di batas suku kata bila bisa
            while _text_w(draw, word, font, stroke, ls) > max_w and sum(c.isalnum() for c in word) >= 9:
                cuts = [c for c in _syllable_cuts(word) if 3 <= c <= len(word) - 3]
                fit = [c for c in cuts if _text_w(draw, word[:c] + "-", font, stroke, ls) <= max_w]
                if fit:
                    cut = max(fit)
                else:
                    cut = len(word) - 4
                    while cut > 4 and _text_w(draw, word[:cut] + "-", font, stroke, ls) > max_w:
                        cut -= 1
                lines.append(word[:cut] + "-")
                word = word[cut:]
            cur = word
        lines.append(cur)
    return [l for l in lines if l is not None]


_VOWELS = set("aeiouAEIOU")


def _syllable_cuts(word: str) -> list[int]:
    """Posisi penggalan yang wajar (pola suku kata Indonesia/Inggris sederhana):
    V|KV  (ke|be)  dan  K|KV  (run|tu), tanpa memisah 'ng', 'ny', 'kh', 'sy'."""
    cuts = []
    w = word
    for i in range(1, len(w) - 1):
        a, b, c = w[i - 1], w[i], w[i + 1]
        if not (a.isalpha() and b.isalpha() and c.isalpha()):
            continue
        if a in _VOWELS and b not in _VOWELS and c in _VOWELS:
            cuts.append(i)                               # ke|be
        elif a not in _VOWELS and b not in _VOWELS and c in _VOWELS:
            if (a + b).lower() not in ("ng", "ny", "kh", "sy", "th", "ch", "sh", "ph", "wh"):
                cuts.append(i)                           # run|tu
    return cuts


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


BUBBLE_PAD = 0.08        # jarak teks dari garis balon (relatif sisi terpendek balon)
SHEAR = 0.2              # kemiringan italic palsu
LINE_SPACING = 1.2       # jarak baris default (lettering manga umumnya 1.15–1.25)


def _light_area(img: np.ndarray, b: TextBlock):
    """Area terang (bagian dalam balon, termasuk balon yang terbuka) di sekitar teks bebas.
    Boleh melebihi kotak (kotak sering lebih sempit dari balonnya), tapi sisi yang 'bocor'
    ke luar (balon terbuka / latar halaman) dipotong di batas kotak.
    Mengembalikan (mask, fx, fy) dalam bingkai yang mungkin lebih besar dari kotak, atau None."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    e = int(max(b.w, b.h) * 0.35)
    fx0, fy0 = max(0, b.x - e), max(0, b.y - e)
    fx1, fy1 = min(W, b.x + b.w + e), min(H, b.y + b.h + e)
    if fx1 - fx0 < 10 or fy1 - fy0 < 10:
        return None
    light = (gray[fy0:fy1, fx0:fx1] >= 200).astype(np.uint8)
    light = cv2.morphologyEx(light, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(light, connectivity=4)
    if n <= 1:
        return None
    if b.text_rect and len(b.text_rect) == 4:
        tx, ty, tw, th = b.text_rect
        cx, cy = int(tx + tw / 2 - fx0), int(ty + th / 2 - fy0)
    else:
        cx, cy = int(b.x + b.w / 2 - fx0), int(b.y + b.h / 2 - fy0)
    cx, cy = min(max(cx, 0), fx1 - fx0 - 1), min(max(cy, 0), fy1 - fy0 - 1)
    i = lbl[cy, cx]
    if not i:
        return None
    m = (lbl == i).astype(np.uint8) * 255
    # sisi yang menyentuh tepi bingkai = bocor keluar balon -> batasi di tepi kotak
    bx, by, bw, bh, _a = st[i]
    lim = np.zeros_like(m)
    lx0 = b.x - fx0 if bx <= 0 else 0
    ly0 = b.y - fy0 if by <= 0 else 0
    lx1 = b.x + b.w - fx0 if bx + bw >= fx1 - fx0 else fx1 - fx0
    ly1 = b.y + b.h - fy0 if by + bh >= fy1 - fy0 else fy1 - fy0
    lim[max(0, ly0):max(0, ly1), max(0, lx0):max(0, lx1)] = 255
    m &= lim
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    full = np.zeros_like(m)
    cv2.drawContours(full, [max(cnts, key=cv2.contourArea)], -1, 255, -1)   # isi lubang (bekas huruf)
    if (full > 0).sum() < 0.15 * b.w * b.h:
        return None
    return full, fx0, fy0


def _shape_mask(b: TextBlock, stroke: int, img: np.ndarray | None = None):
    """Area yang boleh diisi teks, dalam koordinat lokal balon (0,0 = b.x,b.y).
    Balon: bentuk asli (kontur) dikurangi jarak tepi. Teks bebas: kotak dengan sedikit jarak."""
    h, w = max(2, b.h), max(2, b.w)
    m = np.zeros((h, w), np.uint8)
    if b.kind == "bubble" and b.mask_poly:
        pts = np.array(b.mask_poly, np.int32) - np.array([b.x, b.y])
        cv2.fillPoly(m, [pts], 255)
        pad = max(3, int(min(w, h) * BUBBLE_PAD)) + stroke
    elif b.kind == "bubble":
        cv2.ellipse(m, (w // 2, h // 2), (w // 2, h // 2), 0, 0, 360, 255, -1)
        pad = max(3, int(min(w, h) * BUBBLE_PAD * 0.6)) + stroke
    else:
        area = _light_area(img, b) if img is not None and _is_dark(b.color) else None
        if area is not None:
            m, fx, fy = area                          # teks bebas: tempel di area terang (bagian dalam balon)
            pad = max(3, int(min(w, h) * BUBBLE_PAD * 0.8)) + stroke
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * pad + 1, 2 * pad + 1))
            er = cv2.erode(m, k)
            return (er if er.any() else m), fx, fy
        m[:] = 255
        pad = max(2, int(min(w, h) * 0.04)) + stroke
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * pad + 1, 2 * pad + 1))
    er = cv2.erode(m, k)
    return (er if er.any() else m), b.x, b.y


def _is_dark(color: str) -> bool:
    """Warna teks gelap? (teks putih di atas gambar memakai seluruh kotak)."""
    c = (color or "#000000").lstrip("#")
    try:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except ValueError:
        return True
    return (r * 299 + g * 587 + b * 114) / 1000 < 128


class _Shape:
    """Lebar yang tersedia per baris piksel + titik tengah teks (bagian terdalam balon,
    jadi ekor balon tidak menggeser teks)."""

    def __init__(self, mask: np.ndarray, extra_margin: float = 0.0):
        self.h, self.w = mask.shape
        self.x0 = np.full(self.h, -1, np.int32)
        self.x1 = np.full(self.h, -1, np.int32)
        rows = np.nonzero(mask.any(axis=1))[0]
        for y in rows:
            xs = np.nonzero(mask[y])[0]
            self.x0[y], self.x1[y] = xs[0], xs[-1]
        self.ymin, self.ymax = (int(rows[0]), int(rows[-1])) if rows.size else (0, self.h - 1)
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
        cy, cx = np.unravel_index(int(np.argmax(dist)), dist.shape)
        self.cy = int(cy)
        self.cx = (self.x0[cy] + self.x1[cy]) / 2.0 if self.x0[cy] >= 0 else self.w / 2
        self.margin = extra_margin
        self.ay = None
        self.max_w = int(max(1, (self.x1 - self.x0).max())) if rows.size else self.w

    def rooms(self, y0: float, y1: float) -> tuple[float, float]:
        """Ruang ke kiri & ke kanan dari pusat cx (terkecil pada rentang baris y0..y1)."""
        a, b = int(max(0, np.floor(y0))), int(min(self.h - 1, np.ceil(y1)))
        if a > b:
            return -1, -1
        x0, x1 = self.x0[a:b + 1], self.x1[a:b + 1]
        if (x0 < 0).any():
            return -1, -1
        return float((self.cx - x0).min()) - self.margin, float((x1 - self.cx).min()) - self.margin

    def half_room(self, y0: float, y1: float) -> float:
        l, r = self.rooms(y0, y1)
        return min(l, r)

    def anchor(self, ax: float, ay: float):
        """Pakai posisi teks asli sebagai pusat (bila berada di dalam area)."""
        iy = int(round(ay))
        if 0 <= iy < self.h and self.x0[iy] >= 0 and self.x0[iy] <= ax <= self.x1[iy]:
            # jangan terlalu menempel ke satu sisi: geser sedikit ke tengah baris
            mid = (self.x0[iy] + self.x1[iy]) / 2.0
            self.cx = 0.6 * ax + 0.4 * mid
            self.ay = float(ay)


def _fit_shape(draw, text, font_path, shape: _Shape, stroke, ls, line_spacing, max_size, min_size=8,
               fixed: int = 0, shear: float = 0.0):
    """Ukuran font terbesar yang muat di bentuk balon. Mengembalikan (size, lines, top, lh).
    shear: kemiringan italic palsu -- baris atas bergeser ke kanan, baris bawah ke kiri,
    jadi ruang kiri/kanan tiap baris diperiksa terpisah."""
    def place(lines, f, size):
        lh = size * line_spacing
        total = lh * (len(lines) - 1) + size * 1.05
        widths = [_text_w(draw, l, f, stroke, ls) for l in lines]
        tops = []
        if shape.ay is not None:
            tops.append(shape.ay - total / 2)           # posisi teks asli
        tops += [shape.cy - total / 2, (shape.ymin + shape.ymax) / 2 - total / 2]
        tops += [max(shape.ymin, min(t, shape.ymax - total)) for t in list(tops)]
        for top in tops:
            if top < shape.ymin - 1 or top + total > shape.ymax + 1:
                continue
            mid = top + total / 2
            ok = True
            for i, wl in enumerate(widths):
                y0 = top + i * lh + size * 0.12          # bagian huruf yang terlihat
                y1 = top + i * lh + size * 0.95
                left, right = shape.rooms(y0, y1)
                # geser italic: bagian atas huruf ke kanan, bawah ke kiri
                up = shear * (mid - y0)
                down = shear * (y1 - mid)
                if wl / 2 + max(up, -down) > right or wl / 2 + max(down, -up) > left:
                    ok = False
                    break
            if ok:
                return top, lh
        return None

    def try_size(size, allow_break):
        f = _font(font_path, size)
        best = None
        for frac in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.42):
            lines = wrap_text(draw, text, f, int(shape.max_w * frac), stroke, allow_break, ls)
            if not lines:
                continue
            pl = place(lines, f, size)
            if pl:   # pilih susunan yang paling "seimbang" (baris paling sedikit yang masih muat)
                if best is None or len(lines) < len(best[0]):
                    best = (lines, pl)
        return best

    if fixed:
        f = _font(font_path, fixed)
        lines = wrap_text(draw, text, f, int(shape.max_w * 0.9), stroke, True, ls) or [text]
        lh = fixed * line_spacing
        cy = shape.ay if shape.ay is not None else shape.cy
        return fixed, lines, cy - (lh * (len(lines) - 1) + fixed) / 2, lh

    results = {}
    for allow_break in (False, True):
        lo, hi, best = min_size, max_size, None
        while lo <= hi:
            mid = (lo + hi) // 2
            r = try_size(mid, allow_break)
            if r:
                best = (mid, r)
                lo = mid + 1
            else:
                hi = mid - 1
        results[allow_break] = best
    nb, br = results[False], results[True]
    # tanpa memotong kata lebih rapi; potong kata hanya bila hurufnya jadi jauh lebih besar
    pick = nb if nb and (not br or nb[0] >= br[0] * 0.8) else br
    if pick is None:
        f = _font(font_path, min_size)
        lines = wrap_text(draw, text, f, shape.max_w, stroke, True, ls) or [text]
        lh = min_size * line_spacing
        return min_size, lines, shape.cy - (lh * (len(lines) - 1) + min_size) / 2, lh
    size, (lines, (top, lh)) = pick
    return size, lines, top, lh


def render_page(img_bgr: np.ndarray, blocks: list[TextBlock], target_lang: str = "id",
                default_font_path: str = "", uppercase: bool = True, max_size: int = 64,
                italic: bool = True, line_spacing: float = LINE_SPACING, default_size: int = 0,
                default_bold: bool = False) -> np.ndarray:
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)).convert("RGBA")
    measure = ImageDraw.Draw(pil)
    base_font = default_font_path or default_font(target_lang)
    latin = target_lang not in ("ja", "zh", "zh-tw", "ko")

    for b in blocks:
        text = (b.translation or "").strip()
        if not text:
            continue
        case = b.case or ("upper" if uppercase else "none")
        bold = b.bold or (default_bold and not b.preset)   # balon tanpa preset ikut tebal preset 1
        if latin and case == "upper":
            text = text.upper()
        elif latin and case == "lower":
            text = text.lower()
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
        ls = float(b.letter_spacing or 0)
        lsp = float(b.line_spacing or line_spacing)
        smask, fx, fy = _shape_mask(b, stroke, img_bgr)
        shape = _Shape(smask)
        fh, fw = smask.shape
        if b.text_rect and len(b.text_rect) == 4:     # pusatkan di posisi teks asli
            tx, ty, tw, th = b.text_rect
            shape.anchor(tx + tw / 2 - fx, ty + th / 2 - fy)
        if shear:
            shape.margin = 1.0
        fixed = b.font_size if b.font_size > 0 else int(default_size or 0)
        cap = max(max_size, int(min(b.w, b.h) * 0.45)) if not fixed else max_size
        if not fixed and b.src_h:
            # jangan jauh lebih besar dari teks aslinya (narasi di panel lebar jadi raksasa)
            cap = min(cap, max(12, int(b.src_h * (1.9 if b.kind == "bubble" else 1.5))))
        size, lines, top, lh = _fit_shape(measure, text, font_path, shape, stroke, ls, lsp,
                                          min(cap, max(max_size, 8)), fixed=fixed, shear=shear)
        font = _font(font_path, size)

        # gambar di lapisan transparan seukuran balon (+ jarak), lalu miring/putar & geser
        pad = int(size * 1.5) + stroke
        W, H = fw + 2 * pad, fh + 2 * pad
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        widths = [_text_w(d, l, font, stroke, ls) for l in lines]
        block_w = max(widths) if widths else 0
        cx = pad + shape.cx
        grad = _gradient_colors(b)
        fill_mask = Image.new("L", (W, H), 0) if grad else None
        fm = ImageDraw.Draw(fill_mask) if grad else None
        for i, (line, wl) in enumerate(zip(lines, widths)):
            if b.align == "left":
                x = cx - block_w / 2
            elif b.align == "right":
                x = cx + block_w / 2 - wl
            else:
                x = cx - wl / 2
            y = pad + top + i * lh
            # koreksi offset bbox font supaya posisi visual tepat
            l0, t0, _, _ = d.textbbox((0, 0), line, font=font, stroke_width=stroke)
            _draw_line(d, (x - l0, y - t0 * 0.5), line, font, b.color, stroke,
                       b.stroke_color if stroke else None, ls, bold, size)
            if grad:   # isi huruf saja (tanpa stroke) untuk diwarnai gradasi per baris
                _draw_line(fm, (x - l0, y - t0 * 0.5), line, font, 255, 0, None, ls, bold, size)
        if grad:
            layer = _apply_gradient(layer, fill_mask, grad, [pad + top + i * lh for i in range(len(lines))], size)
        if shear:
            cy_l = pad + top + (lh * (len(lines) - 1) + size) / 2
            layer = layer.transform(layer.size, Image.AFFINE, (1, shear, -shear * cy_l, 0, 1, 0),
                                    resample=Image.BICUBIC)
        rot = float(b.rotation or 0)
        if rot:
            cy_l = pad + top + (lh * (len(lines) - 1) + size) / 2
            layer = layer.rotate(rot, resample=Image.BICUBIC, center=(cx, cy_l))
        _paste_clipped(pil, layer, int(fx - pad + (b.dx or 0)), int(fy - pad + (b.dy or 0)))
    return cv2.cvtColor(np.array(pil.convert("RGB")), cv2.COLOR_RGB2BGR)


def _hex_rgb(c: str):
    c = (c or "").lstrip("#")
    try:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except (ValueError, IndexError):
        return None


def _gradient_colors(b: TextBlock):
    if not b.color2:
        return None
    a, z = _hex_rgb(b.color), _hex_rgb(b.color2)
    if a is None or z is None or a == z:
        return None
    return a, z


def _apply_gradient(layer: Image.Image, fill_mask: Image.Image, grad, line_tops, size) -> Image.Image:
    """Warnai isi huruf dengan gradasi atas -> bawah sepanjang blok teks (seperti lettering manhwa)."""
    (r0, g0, b0), (r1, g1, b1) = grad
    W, H = layer.size
    y0 = line_tops[0] + size * 0.1
    y1 = line_tops[-1] + size * 0.95
    if len(line_tops) == 1:
        y0, y1 = line_tops[0] + size * 0.15, line_tops[0] + size * 0.9
    t = np.clip((np.arange(H, dtype=np.float32) - y0) / max(1.0, y1 - y0), 0, 1)
    rows = np.stack([r0 + (r1 - r0) * t, g0 + (g1 - g0) * t, b0 + (b1 - b0) * t, np.full(H, 255.0)], 1)
    img = np.repeat(rows[:, None, :], W, axis=1).astype(np.uint8)
    out = layer.copy()
    out.paste(Image.fromarray(img, "RGBA"), (0, 0), fill_mask)
    return out


def _draw_line(d, xy, line, font, fill, stroke, stroke_fill, ls, bold, size):
    x, y = xy
    off = max(1, size // 28)
    if not ls:
        d.text((x, y), line, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        if bold and not stroke:  # bold palsu untuk font tanpa varian tebal
            d.text((x + off, y), line, font=font, fill=fill)
        return
    for ch in line:   # jarak huruf: gambar per karakter
        d.text((x, y), ch, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        if bold and not stroke:
            d.text((x + off, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + ls


def _paste_clipped(base: Image.Image, layer: Image.Image, x: int, y: int):
    """Tempel lapisan, dipotong bila keluar dari tepi gambar (kiri/atas/kanan/bawah)."""
    cx, cy = max(0, -x), max(0, -y)
    ex = min(layer.width, base.width - x)
    ey = min(layer.height, base.height - y)
    if ex <= cx or ey <= cy:
        return
    base.alpha_composite(layer.crop((cx, cy, ex, ey)), (x + cx, y + cy))
