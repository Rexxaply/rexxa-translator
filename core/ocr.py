"""OCR per blok teks.

- "manga-ocr" : khusus Jepang (vertikal/horizontal, furigana) — paling akurat untuk manga.
- "easyocr"   : Korea, Mandarin, Inggris, dan bahasa lain.
- "auto"      : manga-ocr untuk ja, easyocr untuk sisanya.
"""
from __future__ import annotations

import re

import cv2
import numpy as np
from PIL import Image

from .models import TextBlock

_manga_ocr = None


def _get_manga_ocr():
    global _manga_ocr
    if _manga_ocr is None:
        from manga_ocr import MangaOcr
        _manga_ocr = MangaOcr()
    return _manga_ocr


def _crop(img: np.ndarray, b: TextBlock, pad: int = 4) -> np.ndarray:
    """Potongan gambar untuk OCR. Pakai area teks hasil deteksi bila ada (lebih tepat & tidak ikut
    membaca teks balon tetangga yang menyatu); selain itu seluruh kotak."""
    h, w = img.shape[:2]
    if b.text_rect and len(b.text_rect) == 4:
        x, y, bw, bh = b.text_rect
        # batas potong = kotak balon, tapi jangan sampai memotong teks aslinya sendiri
        bx0, by0 = min(b.x, x), min(b.y, y)
        bx1, by1 = max(b.x + b.w, x + bw), max(b.y + b.h, y + bh)
        # ruang tambahan untuk tanda baca kecil ("…", "!", "?") yang tidak ikut terdeteksi sebagai huruf,
        # tetapi tidak melewati kotak balonnya sendiri (supaya tidak ikut membaca balon tetangga)
        line_h = max(8, min(bw, bh) if bh < bw * 1.3 else min(bw, bh))
        px, py = max(pad, int(line_h * 1.5)), max(pad, int(line_h * 0.5))
        x0, y0 = max(0, bx0, x - px), max(0, by0, y - py)
        x1, y1 = min(w, bx1, x + bw + px), min(h, by1, y + bh + py)
        if x1 - x0 > 4 and y1 - y0 > 4:
            return img[y0:y1, x0:x1]
    x, y, bw, bh = b.x, b.y, b.w, b.h
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)
    return img[y0:y1, x0:x1]


def _text_mask(gray: np.ndarray) -> np.ndarray:
    """Piksel huruf (garis gelap) sebagai 255."""
    _, m = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if m.mean() > 127:                      # teks terang di latar gelap
        m = 255 - m
    return m


def text_angle(crop: np.ndarray) -> float:
    """Kemiringan baris teks (derajat, positif = berlawanan jarum jam / naik ke kanan).
    Dicari sudut yang membuat profil baris horizontal paling 'tajam' (baris & celah jelas)."""
    if crop.size == 0 or min(crop.shape[:2]) < 12:
        return 0.0
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    k = 220.0 / max(gray.shape[:2])
    if k < 1:
        gray = cv2.resize(gray, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    m = _text_mask(gray)
    H, W = m.shape
    # buang garis panel / tepi balon / bintik raster: sisakan komponen seukuran huruf
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros(n, bool)
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if w > 0.6 * W or h > 0.6 * H or a < max(6, H * W * 0.0008):
            continue
        if (x <= 0 or y <= 0 or x + w >= W or y + h >= H) and (w > 0.3 * W or h > 0.3 * H):
            continue                       # potongan garis yang menempel di tepi
        keep[i] = True
    m = np.where(keep[lab], 255, 0).astype(np.uint8)
    if m.mean() < 2:
        return 0.0
    D = int(np.hypot(H, W)) + 4
    canvas = np.zeros((D, D), np.uint8)
    canvas[(D - H) // 2:(D - H) // 2 + H, (D - W) // 2:(D - W) // 2 + W] = m
    c = (D / 2, D / 2)

    def score(a):
        r = cv2.warpAffine(canvas, cv2.getRotationMatrix2D(c, -a, 1.0), (D, D), flags=cv2.INTER_NEAREST)
        rows = r.sum(axis=1, dtype=np.float64)
        return float(np.sum(np.diff(rows) ** 2))

    base = score(0.0)
    angles = np.arange(-40, 40.1, 2.5)
    sc = [score(a) for a in angles]
    a0 = float(angles[int(np.argmax(sc))])
    fine = np.arange(a0 - 2, a0 + 2.01, 0.5)
    sf = [score(a) for a in fine]
    best = float(fine[int(np.argmax(sf))])
    # hanya bila jelas lebih baik daripada tidak diputar
    return best if max(sf) > base * 1.15 and abs(best) >= 3 else 0.0


def fill_hollow(crop: np.ndarray):
    """Huruf berongga (garis tepi hitam, isi putih/terang -- khas judul & SFX komik) diisi gelap
    supaya OCR membacanya seperti huruf biasa. Lubang huruf (O, A, R) tetap terang.
    Mengembalikan gambar baru, atau None bila teksnya bukan huruf berongga."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    dark = _text_mask(gray)
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    H, W = dark.shape
    nw, wl = cv2.connectedComponents(255 - dark, connectivity=4)
    nd, dl = cv2.connectedComponents(dark, connectivity=8)
    if nw < 3 or nw > 400:
        return None
    # tetangga: area putih <-> garis gelap yang bersentuhan
    k = np.ones((3, 3), np.uint8)
    adj = [set() for _ in range(nw)]
    dil = cv2.dilate(dark, k)
    edge = (dil > 0) & (dark == 0)
    wi, di = [], []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            sh = np.roll(np.roll(dl, dy, 0), dx, 1)
            sel = edge & (sh > 0)
            wi.append(wl[sel])
            di.append(sh[sel])
    wi = np.concatenate(wi)
    di = np.concatenate(di)
    pairs = np.unique(np.stack([wi, di], 1), axis=0) if len(wi) else np.zeros((0, 2), int)
    by_dark = {}
    for w_, d_ in pairs:
        by_dark.setdefault(int(d_), set()).add(int(w_))
    for d_, ws in by_dark.items():
        for w_ in ws:
            adj[w_] |= ws
    border = set(np.unique(np.concatenate([wl[0], wl[-1], wl[:, 0], wl[:, -1]])).tolist())
    level = {w_: 0 for w_ in border}
    frontier = list(border)
    while frontier:
        nxt = []
        for w_ in frontier:
            for v in adj[w_]:
                if v not in level:
                    level[v] = level[w_] + 1
                    nxt.append(v)
        frontier = nxt
    odd = np.array([level.get(i, 0) % 2 == 1 for i in range(nw)])
    fill = odd[wl] & (dark == 0)
    if fill.sum() < 0.35 * (dark > 0).sum():      # sedikit area tertutup -> bukan huruf berongga
        return None
    out = np.full((H, W), 255, np.uint8)
    out[(dark > 0) | fill] = 0
    return cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)


def deskew(crop: np.ndarray, angle: float) -> np.ndarray:
    """Putar potongan supaya baris teks mendatar (latar diisi warna tepi)."""
    if not angle:
        return crop
    h, w = crop.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), -angle, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    M[0, 2] += nw / 2 - w / 2
    M[1, 2] += nh / 2 - h / 2
    border = [int(v) for v in np.median(np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]]), axis=0)] \
        if crop.ndim == 3 else int(np.median(crop[[0, -1]]))
    return cv2.warpAffine(crop, M, (nw, nh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
                          borderValue=border)


def _upscale(crop: np.ndarray, target_h: int = 900) -> np.ndarray:
    """Potongan kecil diperbesar (huruf kecil / tipis lebih mudah dibaca)."""
    h = crop.shape[0]
    if h < 120:
        k = min(3.0, 120.0 / max(1, h))
        crop = cv2.resize(crop, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    return crop


def _easy_read(reader, crop: np.ndarray, lang: str):
    """(teks, skor) dari EasyOCR. Baris diurutkan atas->bawah, kiri->kanan."""
    kw = {}
    if lang == "en":
        kw["allowlist"] = ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
                           " .,!?'\"-…:;()&%$#*~/")
    try:
        res = reader.readtext(crop, detail=1, paragraph=False, mag_ratio=1.5 if max(crop.shape[:2]) < 400
                              else 1.0, **kw)
    except TypeError:                          # versi EasyOCR lama
        res = reader.readtext(crop, detail=1, paragraph=False)
    if not res:
        return "", 0.0
    items = []
    for box, txt, conf in res:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((min(ys), max(ys), min(xs), txt, float(conf)))
    items.sort(key=lambda t: (t[0] + t[1]) / 2)
    lines, cur = [], []
    for it in items:                         # kelompokkan per baris
        if cur and (it[0] + it[1]) / 2 > max(c[1] for c in cur) - 0.25 * (it[1] - it[0]):
            lines.append(cur)
            cur = []
        cur.append(it)
    if cur:
        lines.append(cur)
    text = " ".join(" ".join(t[3] for t in sorted(l, key=lambda t: t[2])) for l in lines)
    n = sum(len(t[3]) for t in items) or 1
    conf = sum(t[4] * len(t[3]) for t in items) / n
    return text, conf


def ocr_block(img: np.ndarray, b: TextBlock, engine: str, lang: str, gpu: bool = False) -> str:
    crop = _crop(img, b)
    if crop.size == 0:
        return ""
    if engine == "auto":
        engine = "manga-ocr" if lang == "ja" else "easyocr"

    if engine == "manga-ocr":
        mocr = _get_manga_ocr()
        ang = text_angle(crop) if not b.vertical else 0.0
        pil = Image.fromarray(cv2.cvtColor(deskew(crop, ang) if abs(ang) >= 6 else crop, cv2.COLOR_BGR2RGB))
        text = mocr(pil)
    elif engine == "easyocr":
        from .detector import get_easyocr
        reader = get_easyocr(lang, gpu)
        base = _upscale(crop)
        best = _easy_read(reader, base, lang)
        if best[1] < 0.9:
            # hasil kurang yakin: coba versi yang diluruskan (teks miring) dan versi huruf berongga
            # yang diisi gelap (judul / SFX bergaris tepi), lalu ambil yang paling yakin
            ang = text_angle(crop)
            straight = _upscale(deskew(crop, ang)) if ang else base
            tries = [straight] if ang else []
            filled = fill_hollow(straight)
            if filled is not None:
                tries.append(filled)
            for v in tries:
                t, c = _easy_read(reader, v, lang)
                if t and (c > best[1] + 0.03 or not best[0]):
                    best = (t, c)
        text = best[0]
        b._ocr_conf = float(best[1])
    else:
        raise ValueError(f"Engine OCR tidak dikenal: {engine}")
    text = clean_text(text, lang)
    if lang == "en":
        from . import ocrfix
        text = ocrfix.fix(text, lang)
    return text


def clean_text(text: str, lang: str) -> str:
    text = text.strip()
    if lang in ("ja", "zh", "zh-tw"):
        text = text.replace(" ", "")
        text = re.sub(r"[.．]{2,}|…+", "…", text)
    else:
        # sisa garis balon / panel yang ikut terbaca: "|", "\\", "[", "~" yang berdiri sendiri
        text = re.sub(r"(?:(?<=\s)|^)[|\\/\[\]{}~_=—–<>]+(?=\s|$)", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
    return text


def ocr_page(img: np.ndarray, blocks: list[TextBlock], engine: str, lang: str, gpu: bool = False,
             progress=None):
    errors = []
    for i, b in enumerate(blocks):
        try:
            b.source = ocr_block(img, b, engine, lang, gpu)
        except ImportError:
            raise
        except Exception as e:  # satu blok gagal jangan hentikan halaman
            b.source = ""          # jangan sampai pesan error ikut diterjemahkan/ditempel
            errors.append(str(e))
        if progress:
            progress(i + 1, len(blocks))
    if blocks and len(errors) == len(blocks):
        raise RuntimeError(ocr_error_hint(errors[0]))
    check_language(blocks, lang)
    return blocks


LANG_LABEL = {"ja": "Japanese", "ko": "Korean", "zh": "Chinese", "zh-tw": "Chinese (Traditional)"}


def check_language(blocks, lang):
    """Bahasa asal diset JP/KR/CN tapi hampir semua yang terbaca huruf Latin
    -> hampir pasti salah pilih bahasa (mis. komik bahasa Inggris)."""
    if lang not in LANG_LABEL:
        return
    text = "".join(b.source for b in blocks)
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 8:
        return
    latin = sum(1 for c in letters if c.isascii() or "\uff21" <= c <= "\uff5a")  # termasuk huruf Latin lebar
    if latin / len(letters) > 0.6:
        for b in blocks:
            b.source = ""
        raise RuntimeError(
            f"Teks di halaman ini sepertinya huruf Latin (mis. bahasa Inggris), "
            f"tapi bahasa asal diset ke {LANG_LABEL[lang]}.\n\n"
            f"Ganti pilihan bahasa asal di toolbar (mis. ke EN English), lalu klik ⚡ Terjemahkan lagi.")


def ocr_error_hint(msg: str) -> str:
    if "torchvision::nms" in msg or "torchvision" in msg and "operator" in msg:
        return ("OCR gagal: versi torch dan torchvision tidak cocok, atau torchvision tidak ikut "
                "terbundel ke .exe.\n\nPerbaikan: jalankan fix_torch.bat, lalu build_exe.bat lagi.\n\n"
                f"Detail: {msg}")
    return f"OCR gagal untuk semua blok: {msg}"
