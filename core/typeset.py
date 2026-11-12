"""Typesetting: menulis teks terjemahan ke dalam balon dengan ukuran otomatis."""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import cv2
import math

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


_FONTS_CACHE: dict = {}


def _fonts_key():
    k = []
    for d in (user_fonts_dir(), bundled_fonts_dir(), *SYSTEM_FONT_DIRS):
        try:
            k.append((str(d), d.stat().st_mtime_ns))
        except OSError:
            k.append((str(d), 0))
    return tuple(k)


def list_fonts() -> list[str]:
    """Font milik user + font bawaan aplikasi + font komik yang terpasang di Windows + cadangan.
    Hasil disimpan; dibaca ulang hanya bila isi folder font berubah (font baru ditambah / dihapus)."""
    key = _fonts_key()
    hit = _FONTS_CACHE.get("v")
    if hit is not None and hit[0] == key:
        return list(hit[1])
    out = _list_fonts_scan()
    _FONTS_CACHE["v"] = (key, out)
    return list(out)


def _list_fonts_scan() -> list[str]:
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
    clear_render_cache()
    return str(dst)


def remove_font(path: str):
    p = Path(path).resolve()
    if p.parent != user_fonts_dir().resolve():
        raise FontError("Hanya font yang diinstal lewat aplikasi yang bisa dihapus di sini.")
    p.unlink(missing_ok=True)
    _font.cache_clear()
    clear_render_cache()


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


_W_CACHE: dict = {}


def _text_w(draw, text, font, stroke=0, ls=0.0):
    """Lebar teks (piksel). Disimpan di cache: pencarian ukuran font mengukur kata yang sama
    ribuan kali."""
    if not text:
        return 0
    key = (getattr(font, "path", None) or id(font), getattr(font, "size", 0), text, stroke)
    w = _W_CACHE.get(key)
    if w is None:
        l, t, r, b = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
        w = r - l
        if len(_W_CACHE) > 200_000:
            _W_CACHE.clear()
        _W_CACHE[key] = w
    return w + ls * max(0, len(text) - 1)


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
    H, W = img.shape[:2]
    e = int(max(b.w, b.h) * 0.35)
    fx0, fy0 = max(0, b.x - e), max(0, b.y - e)
    fx1, fy1 = min(W, b.x + b.w + e), min(H, b.y + b.h + e)
    if fx1 - fx0 < 10 or fy1 - fy0 < 10:
        return None
    gray = cv2.cvtColor(img[fy0:fy1, fx0:fx1], cv2.COLOR_BGR2GRAY)     # hanya bagian sekitar teks
    light = (gray >= 200).astype(np.uint8)
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
    if getattr(b, "sfx", False) and b.text_rect:
        # SFX: boleh memakai seluruh area teks aslinya (huruf besar, menimpa gambar seperti aslinya)
        tx, ty, tw, th = (int(v) for v in b.text_rect)
        e = int(min(tw, th) * 0.06)
        m = np.full((th + 2 * e, tw + 2 * e), 255, np.uint8)
        return m, tx - e, ty - e
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
        nz = mask > 0
        has = nz.any(axis=1)
        rows = np.nonzero(has)[0]
        if rows.size:
            self.x0[rows] = nz[rows].argmax(axis=1)
            self.x1[rows] = self.w - 1 - nz[rows][:, ::-1].argmax(axis=1)
        self.ymin, self.ymax = (int(rows[0]), int(rows[-1])) if rows.size else (0, self.h - 1)
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
        cy, cx = np.unravel_index(int(np.argmax(dist)), dist.shape)
        # balon awan / lonjong: titik terdalam bisa di satu "gelembung"; pakai tengah luasnya
        mo = cv2.moments(mask, binaryImage=True)
        if mo["m00"] > 0:
            gy = int(round(mo["m01"] / mo["m00"]))
            if 0 <= gy < self.h and mask[gy].any():
                cy = int(round(0.3 * cy + 0.7 * gy))
        self.cy = int(cy)
        self.cx = (self.x0[cy] + self.x1[cy]) / 2.0 if self.x0[cy] >= 0 else self.w / 2
        self.margin = extra_margin
        self.ay = None
        self._rc = {}
        self.max_w = int(max(1, (self.x1 - self.x0).max())) if rows.size else self.w

    def rooms(self, y0: float, y1: float) -> tuple[float, float]:
        """Ruang ke kiri & ke kanan dari pusat cx (terkecil pada rentang baris y0..y1)."""
        a, b = int(max(0, math.floor(y0))), int(min(self.h - 1, math.ceil(y1)))
        if a > b:
            return -1, -1
        k = (a, b)
        r = self._rc.get(k)
        if r is None:              # (x0 terbesar, x1 terkecil) pada rentang; disimpan per rentang
            x0, x1 = self.x0[a:b + 1], self.x1[a:b + 1]
            r = None if (x0 < 0).any() else (int(x0.max()), int(x1.min()))
            self._rc[k] = r or (None,)
        elif r == (None,):
            r = None
        if r is None:
            return -1, -1
        return float(self.cx - r[0]) - self.margin, float(r[1] - self.cx) - self.margin

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


def _join_all(words, glue, n):
    """Sedikit kata (<= n): satu kata per baris, potongan tanda hubung tetap satu baris."""
    out = []
    for w, g in zip(words, glue):
        if g and out:
            out[-1] += w
        else:
            out.append(w)
    return out


def balance_lines(draw, text: str, font, n: int, stroke: int = 0, ls: float = 0.0, caps=None) -> list[str]:
    """Bagi teks menjadi TEPAT n baris (bila jumlah katanya cukup) dengan lebar serata mungkin.
    Bila teks berisi Enter dan jumlah barisnya sudah n, baris dari pengguna dipakai apa adanya.
    caps: lebar maksimum tiap baris (mis. dari bentuk balon oval) -> baris diisi sebanding dengan
    ruangnya, jadi teks membentuk 'belah ketupat' yang rapi di balon bulat."""
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    if len(paras) == n:
        return paras
    import re as _re
    words, glue = [], []        # kata ber-tanda-hubung boleh dipisah di tanda hubungnya ("DASAR-|DASARMU")
    for w in " ".join(paras).split():
        parts = [p for p in _re.split(r"(?<=[^\W\d_]-)(?=[^\W\d_]{2,})", w) if p]
        for k, p in enumerate(parts):
            words.append(p)
            glue.append(k > 0)
    if not words:
        return [text]
    if len(words) <= n:
        return _join_all(words, glue, n)
    W = len(words)
    width = {}

    def join(i, j):
        out = words[i]
        for k in range(i + 1, j):
            out += ("" if glue[k] else " ") + words[k]
        return out

    def wd(i, j):              # lebar baris berisi kata i..j-1
        k = (i, j)
        if k not in width:
            width[k] = _text_w(draw, join(i, j), font, stroke, ls)
        return width[k]

    INF = float("inf")

    def solve(cost_fn, limit=INF):
        # best[k][j] = (biaya terkecil, potongan) untuk k baris pertama memuat j kata pertama
        best = [[(INF, None)] * (W + 1) for _ in range(n + 1)]
        best[0][0] = (0, None)
        for k in range(1, n + 1):
            for j in range(k, W - (n - k) + 1):
                for i in range(k - 1, j):
                    prev = best[k - 1][i][0]
                    w_ = wd(i, j) / (caps[k - 1] if caps else 1.0)
                    if prev == INF or w_ > limit:
                        continue
                    cost = cost_fn(prev, w_)
                    if cost < best[k][j][0] - 1e-6:
                        best[k][j] = (cost, i)
        if best[n][W][0] == INF:
            return None, INF
        lines, j = [], W
        for k in range(n, 0, -1):
            i = best[k][j][1]
            lines.append(join(i, j))
            j = i
        return lines[::-1], best[n][W][0]

    # 1) baris terlebar sekecil mungkin; 2) di antara susunan yang hampir sama lebarnya,
    #    pilih yang barisnya paling rata (jumlah kuadrat lebar terkecil)
    lines, widest = solve(lambda prev, w_: max(prev, w_))
    if lines is None:
        return [join(0, W)]
    even, _ = solve(lambda prev, w_: prev + w_ * w_, limit=widest * 1.06)
    return even or lines


def _fit_shape(draw, text, font_path, shape: _Shape, stroke, ls, line_spacing, max_size, min_size=8,
               fixed: int = 0, shear: float = 0.0, n_lines: int = 0):
    """Ukuran font terbesar yang muat di bentuk balon. Mengembalikan (size, lines, top, lh).
    shear: kemiringan italic palsu -- baris atas bergeser ke kanan, baris bawah ke kiri,
    jadi ruang kiri/kanan tiap baris diperiksa terpisah."""
    place_memo, wrap_memo = {}, {}

    def place(lines, f, size):
        k = (tuple(lines), size, mode[0], shape.cx)
        if k not in place_memo:
            place_memo[k] = _place(lines, f, size)
        return place_memo[k]

    def wrap(f, size, w, allow_break):
        k = (size, w, allow_break)
        if k not in wrap_memo:
            wrap_memo[k] = wrap_text(draw, text, f, w, stroke, allow_break, ls)
        return wrap_memo[k]

    def _place(lines, f, size):
        lh = size * line_spacing
        total = lh * (len(lines) - 1) + size * 1.05
        widths = [_text_w(draw, l, f, stroke, ls) for l in lines]
        if mode[0] == "anchor":
            # posisi teks asli (sedikit boleh bergeser ke tengah balon)
            tops = [shape.ay + k * (shape.cy - shape.ay) - total / 2 for k in (0, 0.3, 0.6)]
        else:
            tops = [shape.cy - total / 2, (shape.ymin + shape.ymax) / 2 - total / 2]
        tops += [max(shape.ymin, min(t, shape.ymax - total)) for t in list(tops)]
        for top in tops:
            if top < shape.ymin - 1 or top + total > shape.ymax + 1:
                continue
            ok = True
            for i, wl in enumerate(widths):
                y0 = top + i * lh + size * 0.12          # bagian huruf yang terlihat
                y1 = top + i * lh + size * 0.95
                mid = top + i * lh + size * 0.5          # italic dimiringkan per baris
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
        if n_lines:
            lines = balance_lines(draw, text, f, n_lines, stroke, ls)
            pl = place(lines, f, size)
            return (lines, pl) if pl else None
        best = None
        for frac in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.42):
            lines = wrap(f, size, int(shape.max_w * frac), allow_break)
            if not lines:
                continue
            pl = place(lines, f, size)
            if pl:   # pilih susunan yang paling "seimbang" (baris paling sedikit yang masih muat)
                if best is None or len(lines) < len(best[0]):
                    best = (lines, pl)
        return best

    if fixed:
        f = _font(font_path, fixed)
        lines = (balance_lines(draw, text, f, n_lines, stroke, ls) if n_lines else
                 wrap_text(draw, text, f, int(shape.max_w * 0.9), stroke, True, ls)) or [text]
        lh = fixed * line_spacing
        cy = shape.ay if shape.ay is not None else shape.cy
        return fixed, lines, cy - (lh * (len(lines) - 1) + fixed) / 2, lh

    def search(allow_break):
        lo, hi, best = min_size, max_size, None
        while lo <= hi:
            mid = (lo + hi) // 2
            r = try_size(mid, allow_break)
            if r:
                best = (mid, r)
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    def better(a, b, ratio):     # a diutamakan bila ukurannya tidak jauh lebih kecil dari b
        return a if a and (not b or a[0] >= b[0] * ratio) else b

    mode = ["any"]
    if n_lines:
        free = search(True)
        if shape.ay is not None:
            mode[0] = "anchor"
            free = better(search(True), free, 0.85)
        if free:
            size, (lines, (top, lh)) = free
            return size, lines, top, lh
        # baris pilihan pengguna tidak muat di bentuk balon: cukup muat di kotaknya
        size = max_size
        while size > min_size:
            f = _font(font_path, size)
            lines = balance_lines(draw, text, f, n_lines, stroke, ls)
            lh = size * line_spacing
            if (max(_text_w(draw, l, f, stroke, ls) for l in lines) <= shape.max_w
                    and lh * (len(lines) - 1) + size * 1.05 <= shape.ymax - shape.ymin):
                break
            size -= 1
        f = _font(font_path, size)
        lines = balance_lines(draw, text, f, n_lines, stroke, ls)
        lh = size * line_spacing
        return size, lines, shape.cy - (lh * (len(lines) - 1) + size) / 2, lh
    results = {}
    for allow_break in (False, True):
        mode[0] = "any"
        free = search(allow_break)
        if shape.ay is not None:
            mode[0] = "anchor"
            # di posisi teks asli, kecuali hurufnya jadi jauh lebih kecil
            free = better(search(allow_break), free, 0.85)
        results[allow_break] = free
    nb, br = results[False], results[True]
    # tanpa memotong kata lebih rapi; potong kata hanya bila hurufnya jadi jauh lebih besar
    pick = nb if nb and (not br or nb[0] >= br[0] * 0.8) else br
    if pick is None:
        f = _font(font_path, min_size)
        lines = wrap_text(draw, text, f, shape.max_w, stroke, True, ls) or [text]
        lh = min_size * line_spacing
        return min_size, lines, shape.cy - (lh * (len(lines) - 1) + min_size) / 2, lh
    size, (lines, (top, lh)) = pick
    # rapikan: bagi ulang kata supaya tiap baris mengisi ruangnya secara seimbang (mengikuti bentuk
    # balon: baris tengah lebih panjang dari atas/bawah), tanpa baris yatim / potongan kata
    if len(lines) >= 2 and "\n" not in text and " " in text and not any(ord(c) > 0x2E80 for c in text):
        mode[0] = "anchor" if shape.ay is not None else "any"
        # potongan kata buatan (bukan tanda hubung asli seperti "DASAR-DASARMU")
        broken = any(l.endswith("-") and (l + lines[i + 1].split(" ")[0]) not in text.upper()
                     and (l + lines[i + 1].split(" ")[0]) not in text
                     for i, l in enumerate(lines[:-1]))
        # kata terpotong ("KEMAM-/PUANMU") boleh ditukar huruf sedikit lebih kecil (maks. -22%)
        low = int(size * 0.78) if broken else size
        done = False
        for sz in range(size, max(min_size, low) - 1, -1):
            f = _font(font_path, sz)
            lh_ = sz * line_spacing
            best_pick = None
            for n in (len(lines) - 1, len(lines), len(lines) + 1):
                if n < 1 or n > len(text.split()):
                    continue
                total = lh_ * (n - 1) + sz * 1.05
                cy = (shape.ay if shape.ay is not None else shape.cy)
                t0 = max(shape.ymin, min(cy - total / 2, shape.ymax - total))
                caps = []
                for i in range(n):
                    y0, y1 = t0 + i * lh_ + sz * 0.12, t0 + i * lh_ + sz * 0.95
                    left, right = shape.rooms(y0, y1)
                    caps.append(max(1.0, 2 * min(left, right) - shear * sz))
                bl = balance_lines(draw, text, f, n, stroke, ls, caps=caps)
                if len(bl) != n:
                    continue
                pl = place(bl, f, sz)
                if pl:
                    fill = max(_text_w(draw, l, f, stroke, ls) / c for l, c in zip(bl, caps))
                    # utamakan jumlah baris semula; 1 baris lebih sedikit bila tetap lega
                    score = abs(n - len(lines)) * 0.25 + (fill if fill > 0.92 else 0)
                    if best_pick is None or score < best_pick[0]:
                        best_pick = (score, bl, pl)
            if best_pick:
                size, lines, (top, lh) = sz, best_pick[1], best_pick[2]
                done = True
                break
        if not done and broken:
            pass                                   # tetap pakai susunan dengan potongan kata
    return size, lines, top, lh


def render_page(img_bgr: np.ndarray, blocks: list[TextBlock], target_lang: str = "id",
                default_font_path: str = "", uppercase: bool = True, max_size: int = 64,
                italic: bool = True, line_spacing: float = LINE_SPACING, default_size: int = 0,
                default_bold: bool = False, harmonize: bool = True, collect: list | None = None) -> np.ndarray:
    """harmonize: ukuran huruf otomatis diseragamkan antar balon di halaman yang sama -- balon
    yang teks aslinya seukuran tidak boleh jauh lebih besar dari balon lainnya (lebih rapi)."""
    args = (img_bgr, blocks, target_lang, default_font_path, uppercase, max_size, italic, line_spacing,
            default_size, default_bold)
    for b in blocks:
        b._cap = 0
    auto = [b for b in blocks if (b.translation or "").strip() and b.kind in ("bubble", "free")
            and not getattr(b, "sfx", False) and not (b.font_size > 0 or default_size) and b.src_h]
    if harmonize and len(auto) >= 2:
        _render_page(*args, dry=True)
        for b in auto:
            peers = [o.fit_size for o in auto if o.kind == b.kind and o.fit_size
                     and 0.75 <= o.src_h / b.src_h <= 1.33]
            if len(peers) >= 2:
                ref = float(np.median(peers))
                b._cap = int(max(ref * 1.06, min(b.fit_size, b.src_h * 1.05)))
    return _render_page(*args, dry=False, collect=collect)


_LAYOUT_CACHE: "OrderedDict" = None
_LAYER_CACHE: "OrderedDict" = None
_LAYER_BYTES = [0]
LAYER_CACHE_MB = 64          # diperkecil otomatis di mode hemat (perf.apply)


def clear_render_cache():
    global _LAYOUT_CACHE, _LAYER_CACHE
    _LAYOUT_CACHE, _LAYER_CACHE = None, None
    _LAYER_BYTES[0] = 0
    _W_CACHE.clear()


import threading as _th
_RC_LOCK = _th.Lock()


def _cache_get(cache, key):
    if cache is None:
        return None
    with _RC_LOCK:
        v = cache.get(key)
        if v is not None:
            cache.move_to_end(key)
    return v


def _layout_put(key, val):
    global _LAYOUT_CACHE
    from collections import OrderedDict
    with _RC_LOCK:
        if _LAYOUT_CACHE is None:
            _LAYOUT_CACHE = OrderedDict()
        _LAYOUT_CACHE[key] = val
        while len(_LAYOUT_CACHE) > 600:
            _LAYOUT_CACHE.popitem(last=False)


def _layer_put(key, layer, pad):
    global _LAYER_CACHE
    from collections import OrderedDict
    if _LAYER_CACHE is None:
        _LAYER_CACHE = OrderedDict()
    nb = layer.width * layer.height * 4
    limit = LAYER_CACHE_MB * 1024 * 1024
    if nb > limit // 4:
        return
    with _RC_LOCK:
        old = _LAYER_CACHE.pop(key, None)
        if old is not None:
            _LAYER_BYTES[0] -= old[0].width * old[0].height * 4
        _LAYER_CACHE[key] = (layer, pad)
        _LAYER_BYTES[0] += nb
        while _LAYER_BYTES[0] > limit and _LAYER_CACHE:
            _, (ly, _p) = _LAYER_CACHE.popitem(last=False)
            _LAYER_BYTES[0] -= ly.width * ly.height * 4


def _region_sig(img: np.ndarray, b: TextBlock) -> int:
    """Sidik isi gambar di sekitar teks bebas (bentuk area terangnya bergantung pada gambar)."""
    import zlib
    H, W = img.shape[:2]
    e = int(max(b.w, b.h) * 0.35)
    crop = img[max(0, b.y - e):min(H, b.y + b.h + e), max(0, b.x - e):min(W, b.x + b.w + e)]
    return zlib.crc32(np.ascontiguousarray(crop).data) if crop.size else 0


def _layout(measure, b, text, font_path, stroke, ls, lsp, cap, max_size, fixed, shear, img_bgr):
    """Ukuran & susunan baris satu balon -> (size, lines, top, lh, cx, fx, fy, fw, fh)."""
    smask, fx, fy = _shape_mask(b, stroke, img_bgr)
    shape = _Shape(smask)
    fh, fw = smask.shape
    if b.text_rect and len(b.text_rect) == 4:     # pusatkan di posisi teks asli
        tx, ty, tw, th = b.text_rect
        shape.anchor(tx + tw / 2 - fx, ty + th / 2 - fy)
    if shear:
        shape.margin = 1.0
    n_lines = max(0, int(getattr(b, "max_lines", 0) or 0))
    size, lines, top, lh = _fit_shape(measure, text, font_path, shape, stroke, ls, lsp,
                                      (cap if getattr(b, "sfx", False) else min(cap, max(max_size, 8))),
                                      fixed=fixed, shear=shear, n_lines=n_lines)
    if not fixed and b.src_h and size < (0.72 if b.kind == "bubble" else 0.85) * b.src_h \
            and b.kind in ("bubble", "free"):
        # bentuk balon yang terdeteksi terlalu sempit (mis. hanya cahaya putih di sekitar teks):
        # pakai seluruh kotak supaya huruf tidak jauh lebih kecil dari teks aslinya
        rect = np.zeros_like(smask)
        # hanya di dalam kotak blok (bingkai area terang bisa lebih besar dari kotaknya)
        rx0, ry0 = max(0, b.x - fx), max(0, b.y - fy)
        rx1, ry1 = min(fw, b.x + b.w - fx), min(fh, b.y + b.h - fy)
        mh, mw = max(1, int((ry1 - ry0) * 0.05)), max(1, int((rx1 - rx0) * 0.06))
        rect[ry0 + mh:max(ry0 + mh + 1, ry1 - mh), rx0 + mw:max(rx0 + mw + 1, rx1 - mw)] = 255
        shape2 = _Shape(rect)
        if b.text_rect and len(b.text_rect) == 4:
            tx, ty, tw, th = b.text_rect
            shape2.anchor(tx + tw / 2 - fx, ty + th / 2 - fy)
        if shear:
            shape2.margin = 1.0
        cap2 = min(cap, max(max_size, 8))
        alt = _fit_shape(measure, text, font_path, shape2, stroke, ls, lsp,
                         cap2, fixed=0, shear=shear, n_lines=n_lines)
        if alt[0] > size * 1.15:
            size, lines, top, lh = alt
            shape = shape2
    return int(size), tuple(lines), float(top), float(lh), float(shape.cx), int(fx), int(fy), fw, fh


def _render_page(img_bgr: np.ndarray, blocks: list[TextBlock], target_lang: str = "id",
                 default_font_path: str = "", uppercase: bool = True, max_size: int = 64,
                 italic: bool = True, line_spacing: float = LINE_SPACING, default_size: int = 0,
                 default_bold: bool = False, dry: bool = False, collect: list | None = None) -> np.ndarray | None:
    """Cepat saat menyunting: tata letak (ukuran font + baris) dan gambar teks tiap balon disimpan
    di cache -- balon yang tidak berubah tidak dihitung / digambar ulang, dan menggeser teks (dx/dy)
    hanya menempel ulang. Teks ditempel langsung ke gambar (tanpa konversi seluruh halaman)."""
    measure = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    base_font = default_font_path or default_font(target_lang)
    latin = target_lang not in ("ja", "zh", "zh-tw", "ko")
    out = None if dry else img_bgr.copy()

    for b in blocks:
        text = (b.translation or "").strip()
        if not text or b.kind in ("title", "image"):
            continue
        case = b.case or ("upper" if uppercase else "none")
        if not b.case and case == "upper" and latin:
            # teks asli huruf kecil-besar biasa (narasi / gumaman "I feel chilly...") -> jangan dikapitalkan
            src_letters = [c for c in (b.source or "") if c.isalpha()]
            if len(src_letters) >= 6 and sum(c.islower() for c in src_letters) > 0.5 * len(src_letters):
                case = "none"
        bold = b.bold or (default_bold and not b.preset)   # balon tanpa preset ikut tebal preset 1
        if latin and case == "upper":
            text = text.upper()
        elif latin and case == "lower":
            text = text.lower()
        font_path = b.font or base_font
        text = _fix_glyphs(text, font_path)
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
        lsp = float(b.line_spacing or (1.0 if getattr(b, "sfx", False) else line_spacing))
        fixed = b.font_size if b.font_size > 0 else int(default_size or 0)
        cap = max(max_size, int(min(b.w, b.h) * 0.45)) if not fixed else max_size
        if not fixed and b.src_h:
            # jangan jauh lebih besar dari teks aslinya (narasi di panel lebar jadi raksasa)
            k = 1.45 if b.kind == "bubble" else (1.45 if getattr(b, "sfx", False) else 1.15)
            cap = min(cap, max(12, int(b.src_h * k)))
            if getattr(b, "sfx", False):
                cap = max(cap, min(int(b.src_h * 1.45), 400))   # SFX boleh melebihi batas ukuran maksimum
        if getattr(b, "_cap", 0) and not fixed:
            cap = min(cap, b._cap)
        dark = _is_dark(b.color)
        sig = _region_sig(img_bgr, b) if (b.kind not in ("bubble",) and dark
                                          and not (getattr(b, "sfx", False) and b.text_rect)) else 0
        poly = hash(tuple(tuple(p) for p in b.mask_poly)) if b.mask_poly else 0
        lkey = (text, font_path, stroke, ls, lsp, fixed, cap, max_size, shear,
                int(getattr(b, "max_lines", 0) or 0), b.kind, bool(getattr(b, "sfx", False)),
                b.x, b.y, b.w, b.h, tuple(b.text_rect or ()), poly, b.src_h, dark, sig)
        lay = _cache_get(_LAYOUT_CACHE, lkey)
        if lay is None:
            lay = _layout(measure, b, text, font_path, stroke, ls, lsp, cap, max_size, fixed, shear, img_bgr)
            _layout_put(lkey, lay)
        size, lines, top, lh, scx, fx, fy, fw, fh = lay
        b.fit_size = int(size)
        b._fit_lines = len(lines)          # info untuk panel (tombol +/− baris)
        if dry:
            continue
        rot = float(b.rotation or 0)
        ckey = (lkey, lay, b.color, b.color2, b.grad_type, b.grad_angle, b.grad_pos, b.grad_soft,
                b.grad_scope, b.stroke_color if stroke else "", b.align, bool(bold), rot)
        got = _cache_get(_LAYER_CACHE, ckey)
        if got is None:
            layer, pad = _draw_block(b, lines, font_path, size, top, lh, scx, fw, fh, stroke, ls, bold, shear, rot)
            _layer_put(ckey, layer, pad)
        else:
            layer, pad = got
        px, py = int(fx - pad + (b.dx or 0)), int(fy - pad + (b.dy or 0))
        _paste_np(out, layer, px, py)
        if collect is not None:          # lapisan teks per balon (export PSD)
            ox, oy = getattr(layer, "_off", (0, 0))
            collect.append((b, layer, px + ox, py + oy))
    return out


def _draw_block(b, lines, font_path, size, top, lh, scx, fw, fh, stroke, ls, bold, shear, rot):
    """Gambar teks satu balon di lapisan transparan seukuran balon (+ jarak), lalu miring/putar."""
    font = _font(font_path, size)
    pad = int(size * 1.5) + stroke
    W, H = fw + 2 * pad, fh + 2 * pad
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    widths = [_text_w(d, l, font, stroke, ls) for l in lines]
    block_w = max(widths) if widths else 0
    cx = pad + scx
    grad = _gradient_colors(b)
    fill_mask = Image.new("L", (W, H), 0) if grad else None
    fm = ImageDraw.Draw(fill_mask) if grad else None
    boxes = []
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
        if grad:   # isi huruf saja (tanpa stroke) untuk diwarnai gradasi
            _draw_line(fm, (x - l0, y - t0 * 0.5), line, font, 255, 0, None, ls, bold, size)
            sx = shear * size * 0.6
            boxes.append((x - sx, y + size * 0.08, x + wl + sx, y + size * 0.95))
    line_tops = [pad + top + i * lh for i in range(len(lines))]
    if shear:   # miringkan tiap baris di sekitar titik tengahnya sendiri (tetap rata tengah)
        layer = _shear_lines(layer, line_tops, size, lh, shear)
        if grad:
            fill_mask = _shear_lines(fill_mask, line_tops, size, lh, shear)
    if grad:
        layer = _apply_gradient(layer, fill_mask, grad, boxes, b)
    if rot:
        cy_l = pad + top + (lh * (len(lines) - 1) + size) / 2
        layer = layer.rotate(rot, resample=Image.BICUBIC, center=(cx, cy_l))
    # simpan hanya bagian yang berisi huruf (lebih hemat memori & cepat ditempel)
    bbox = layer.getbbox()
    if not bbox:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0)), pad
    if bbox != (0, 0, W, H):
        layer = layer.crop(bbox)
        layer._off = (bbox[0], bbox[1])
    return layer, pad


def _paste_np(base: np.ndarray, layer: Image.Image, x: int, y: int):
    """Tempel lapisan RGBA ke gambar BGR (numpy), dipotong di tepi gambar."""
    ox, oy = getattr(layer, "_off", (0, 0))
    x, y = x + ox, y + oy
    H, W = base.shape[:2]
    lw, lh = layer.size
    cx, cy = max(0, -x), max(0, -y)
    ex, ey = min(lw, W - x), min(lh, H - y)
    if ex <= cx or ey <= cy:
        return
    arr = np.asarray(layer)[cy:ey, cx:ex]
    a = arr[..., 3:4]
    if not a.any():
        return
    roi = base[y + cy:y + ey, x + cx:x + ex]
    rgb = arr[..., 2::-1].astype(np.uint16)         # RGB -> BGR
    af = a.astype(np.uint16)
    roi[...] = ((rgb * af + roi.astype(np.uint16) * (255 - af) + 127) // 255).astype(np.uint8)


def _shear_lines(img: Image.Image, line_tops, size, lh, shear) -> Image.Image:
    """Italic palsu per baris: setiap baris dimiringkan terhadap tengah barisnya sendiri."""
    out = img.copy()
    H = img.height
    n = len(line_tops)
    for i, t in enumerate(line_tops):
        c = t + size * 0.5
        a = 0 if i == 0 else int(round((line_tops[i - 1] + size * 0.5 + c) / 2))
        z = H if i == n - 1 else int(round((c + line_tops[i + 1] + size * 0.5) / 2))
        if z <= a:
            continue
        strip = img.crop((0, a, img.width, z))
        bb = strip.getbbox()
        if not bb:
            continue
        # hanya bagian yang berisi huruf (+ jarak geser) yang dimiringkan -> jauh lebih cepat
        m = int(abs(shear) * (z - a)) + 4
        l, r = max(0, bb[0] - m), min(img.width, bb[2] + m)
        part = strip.crop((l, 0, r, z - a))
        sh = part.transform(part.size, Image.AFFINE, (1, shear, -shear * (c - a), 0, 1, 0),
                            resample=Image.BICUBIC)
        out.paste(Image.new("RGBA", (r - l, z - a), (0, 0, 0, 0)) if img.mode == "RGBA" else
                  Image.new(img.mode, (r - l, z - a), 0), (l, a))
        out.paste(sh, (l, a))
    return out


_GLYPH_ALT = {"—": "-", "–": "-", "‐": "-", "‑": "-", "―": "-", "…": "...", "“": '"', "”": '"',
              "‘": "'", "’": "'", "«": '"', "»": '"', "～": "~", "！": "!", "？": "?", "♡": "<3", "♥": "<3"}


@lru_cache(maxsize=64)
def _cmap(font_path: str):
    """Kode karakter yang dimiliki font (fontTools), atau None bila tidak bisa dibaca."""
    try:
        from fontTools.ttLib import TTFont
        kw = {"fontNumber": 0} if font_path.lower().endswith(".ttc") else {}
        t = TTFont(font_path, lazy=True, **kw)
        cm = t.getBestCmap() or {}
        t.close()
        return frozenset(cm.keys())
    except Exception:
        return None


@lru_cache(maxsize=256)
def _missing_glyphs(font_path: str, chars: str) -> frozenset:
    """Karakter yang tidak ada di font (akan tampil sebagai kotak kosong / 'tofu')."""
    cm = _cmap(font_path)
    if cm is not None:
        return frozenset(c for c in chars if ord(c) not in cm)
    # cadangan tanpa fontTools: bandingkan dengan glyph kotak .notdef
    try:
        f = ImageFont.truetype(font_path, 40)
        g = f.getmask("\U0010FFFD")
        tofu = (g.size, bytes(g))
        return frozenset(c for c in chars if (f.getmask(c).size, bytes(f.getmask(c))) == tofu)
    except Exception:
        return frozenset()


def _fix_glyphs(text: str, font_path: str) -> str:
    special = "".join(sorted({c for c in text if ord(c) > 127}))
    if not special or not font_path:
        return text
    miss = _missing_glyphs(font_path, special)
    for c in miss:
        text = text.replace(c, _GLYPH_ALT.get(c, ""))
    return text


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


def _apply_gradient(layer: Image.Image, fill_mask: Image.Image, grad, boxes, b: TextBlock) -> Image.Image:
    """Warnai isi huruf dengan gradasi (jenis, arah, posisi, kehalusan seperti Photoshop).
    boxes = kotak tiap baris [(x0, y0, x1, y1)] di koordinat lapisan."""
    from . import gradient as G
    c1, c2 = grad
    W, H = layer.size
    paint = np.zeros((H, W, 4), np.uint8)
    kind = getattr(b, "grad_type", "linear") or "linear"
    ang = float(getattr(b, "grad_angle", 90.0) if getattr(b, "grad_angle", None) is not None else 90.0)
    pos = float(getattr(b, "grad_pos", 0.5) if getattr(b, "grad_pos", None) is not None else 0.5)
    soft = float(getattr(b, "grad_soft", 1.0) if getattr(b, "grad_soft", None) is not None else 1.0)
    regions = boxes if getattr(b, "grad_scope", "block") == "line" else [
        (min(x[0] for x in boxes), min(x[1] for x in boxes), max(x[2] for x in boxes), max(x[3] for x in boxes))]
    # isi seluruh lapisan dengan warna ujung dulu (bagian huruf di luar kotak tetap berwarna)
    paint[...] = G.colorize(np.zeros((1, 1), np.float32), c1, c2)[0, 0]
    for x0, y0, x1, y1 in regions:
        x0, y0 = max(0, int(x0)), max(0, int(y0))
        x1, y1 = min(W, int(np.ceil(x1))), min(H, int(np.ceil(y1)))
        if x1 <= x0 or y1 <= y0:
            continue
        t = G.field(x1 - x0, y1 - y0, kind, ang, pos, soft)
        paint[y0:y1, x0:x1] = G.colorize(t, c1, c2)
    out = layer.copy()
    out.paste(Image.fromarray(paint, "RGBA"), (0, 0), fill_mask)
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
