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
    return _group_items(res)


def _group_items(res):
    """Hasil EasyOCR [(kotak, teks, conf)] -> (teks per baris atas->bawah, conf rata-rata)."""
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
    # baris dipisah "\n" (jumlah baris dipakai untuk memeriksa apakah ada baris yang terlewat)
    text = "\n".join(" ".join(t[3] for t in sorted(l, key=lambda t: t[2])) for l in lines)
    n = sum(len(t[3]) for t in items) or 1
    conf = sum(t[4] * len(t[3]) for t in items) / n
    return text, conf


def _expected_chars(b: TextBlock) -> float:
    """Perkiraan jumlah huruf di blok dari panjang baris-baris teksnya (0 = tidak diketahui)."""
    n = getattr(b, "_letters", 0) or 0          # huruf yang terlihat saat deteksi
    if n:
        return float(n)
    lines = getattr(b, "_lines", None) or []
    if lines:
        return sum(w / max(1.0, h * 0.62) for _, _, w, h in lines)
    return 0.0


def _score(text: str, conf: float, lang: str, expect: float = 0.0) -> float:
    """Nilai mutu hasil baca: keyakinan OCR + (untuk Inggris) seberapa banyak kata yang dikenal,
    dikurangi bila jumlah hurufnya jauh lebih sedikit dari panjang teks di gambar (baris hilang)."""
    t = clean_text(text or "", lang)
    if not t:
        return 0.0
    cover = 1.0
    if expect >= 3:
        n = sum(1 for c in t if c.isalnum())
        cover = min(1.0, n / (expect * 0.95))
    if lang != "en":
        return float(conf) * cover
    from . import ocrfix
    words = [w for w in re.findall(r"[A-Za-z']+", t) if len(w.strip("'")) >= 2]
    if not words:
        return float(conf) * 0.8 * cover
    known = sum(1 for w in words if ocrfix._known(w.strip("'")) or ocrfix._known(ocrfix.fix(w).strip("'!")))
    return (0.55 * float(conf) + 0.45 * known / len(words)) * cover


def _denoise(crop: np.ndarray):
    """Latar raster / arsiran / butiran: bintik kecil dihapus, huruf dipertegas (hitam di atas putih)."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    g = cv2.medianBlur(gray, 3)
    m = _text_mask(g)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(m, 8)
    h = crop.shape[0]
    keep = np.zeros(n, bool)
    for i in range(1, n):
        x, y, w, hh, a = st[i]
        keep[i] = a >= max(6, h * h * 0.0004) or hh >= h * 0.08
    clean = np.where(keep[lbl], 0, 255).astype(np.uint8)
    return cv2.cvtColor(clean, cv2.COLOR_GRAY2BGR)


def _allow(lang):
    if lang == "en":
        return ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
                " .,!?'\"-…:;()&%$#*~/")
    return None


def _fast_lines(reader, img: np.ndarray, b: TextBlock, lang: str):
    """CEPAT: baca langsung tiap baris hasil deteksi dengan pengenal huruf EasyOCR (recognize),
    tanpa tahap pencarian teks (CRAFT) yang paling berat di CPU. Semua baris dibaca sekaligus
    (satu batch). None bila tidak bisa (tidak ada posisi baris / versi EasyOCR lain)."""
    lines = sorted(getattr(b, "_lines", None) or [], key=lambda r: r[1] + r[3] / 2)
    if not lines or b.vertical or not hasattr(reader, "recognize"):
        return None
    H, W = img.shape[:2]
    hs = sorted(r[3] for r in lines)
    mh = max(4, hs[len(hs) // 2])
    boxes = []
    for x, y, w, h in lines:
        px, py = int(h * 0.6) + 2, int(h * 0.3) + 2
        boxes.append((max(0, x - px), max(0, y - py), min(W, x + w + px), min(H, y + h + py)))
    X0, Y0 = min(r[0] for r in boxes), min(r[1] for r in boxes)
    X1, Y1 = max(r[2] for r in boxes), max(r[3] for r in boxes)
    piece = img[Y0:Y1, X0:X1]
    if piece.size == 0:
        return None
    gray = cv2.cvtColor(piece, cv2.COLOR_BGR2GRAY) if piece.ndim == 3 else piece
    k = min(3.0, 48.0 / mh) if mh < 40 else 1.0      # huruf kecil diperbesar (model memakai tinggi 64)
    if k > 1.0:
        gray = cv2.resize(gray, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    hl = [[int((x0 - X0) * k), int((x1 - X0) * k), int((y0 - Y0) * k), int((y1 - Y0) * k)]
          for x0, y0, x1, y1 in boxes]
    kw = {"allowlist": _allow(lang)} if _allow(lang) else {}
    try:
        res = reader.recognize(gray, horizontal_list=hl, free_list=[], detail=1, paragraph=False,
                               batch_size=max(1, len(hl)), **kw)
    except Exception:
        return None
    t, c = _group_items(res)
    return (t, c) if t.strip() else None


def _line_read(reader, img: np.ndarray, b: TextBlock, lang: str):
    """Baca per BARIS memakai posisi baris dari deteksi: urutan baca pasti atas -> bawah dan
    setiap potongan hanya berisi satu baris (lebih akurat untuk balon oval / teks rapat)."""
    lines = sorted(getattr(b, "_lines", None) or [], key=lambda r: r[1] + r[3] / 2)
    if len(lines) < 2 or b.vertical:
        return None
    H, W = img.shape[:2]
    texts, confs, total = [], [], 0
    for x, y, w, h in lines:
        px, py = int(h * 0.9), int(h * 0.35)
        x0, y0 = max(0, x - px), max(0, y - py)
        x1, y1 = min(W, x + w + px), min(H, y + h + py)
        piece = img[y0:y1, x0:x1]
        if piece.size == 0:
            continue
        t, c = _easy_read(reader, _upscale(piece), lang)
        t = " ".join(t.split())
        if t.strip():
            texts.append(t.strip())
            confs.append(c * len(t))
            total += len(t)
    if not texts:
        return None
    return "\n".join(texts), sum(confs) / max(1, total)


def _best_read(reader, img: np.ndarray, b: TextBlock, crop: np.ndarray, lang: str):
    """Baca bertahap, berhenti segera setelah hasilnya meyakinkan:
    1) seluruh blok  2) per baris  3) diluruskan (teks miring)  4) bintik raster dibuang
    5) huruf berongga diisi. Dipilih hasil dengan nilai mutu (_score) tertinggi."""
    from . import perf
    good = 0.72
    max_tries = 3 if perf.low_end() else 5
    expect = _expected_chars(b)
    n_lines = len(getattr(b, "_lines", None) or [])
    fast = _fast_lines(reader, img, b, lang)
    if fast:
        sc = _score(fast[0], fast[1], lang, expect)
        got = sum(1 for ln in fast[0].split("\n") if any(ch.isalnum() for ch in ln))
        if sc >= good + 0.05 and got >= n_lines:
            return fast                     # sudah meyakinkan: tidak perlu deteksi teks (CRAFT)
    base = _upscale(crop)
    t, c = _easy_read(reader, base, lang)
    best = (t, c, _score(t, c, lang, expect))
    tries = 1

    pool = [(t, c)]

    def consider(res):
        nonlocal best
        if res and res[0].strip():
            pool.append(res)
            sc = _score(res[0], res[1], lang, expect)
            if sc > best[2] + 0.02 or not best[0].strip():
                best = (res[0], res[1], sc)

    if fast:
        consider(fast)                      # hasil baca per baris (cepat) ikut dibandingkan
    got_lines = sum(1 for ln in best[0].split("\n") if any(ch.isalnum() for ch in ln))
    missed = n_lines >= 2 and got_lines < n_lines
    if not fast and (best[2] < good or missed):
        # ada baris yang tidak terbaca (mis. baris pendek "IT..." / "AH...") -> baca per baris
        consider(_line_read(reader, img, b, lang))
        tries += 1
    ang = None
    if best[2] < good and tries < max_tries:
        ang = text_angle(crop)
        if ang:
            consider(_easy_read(reader, _upscale(deskew(crop, ang)), lang))
            tries += 1
    straight = _upscale(deskew(crop, ang)) if ang else base
    if best[2] < good and tries < max_tries:
        consider(_easy_read(reader, _denoise(straight), lang))
        tries += 1
    if best[2] < good and tries < max_tries:
        filled = fill_hollow(straight)
        if filled is not None:
            consider(_easy_read(reader, filled, lang))
    text = best[0]
    if lang == "en" and len(pool) > 1:
        text = _merge_words(text, [p[0] for p in pool if p[0] != best[0]])
    return text, best[1]


def _merge_words(main: str, others: list[str]) -> str:
    """Gabungkan hasil beberapa kali baca: kata di hasil terbaik yang TIDAK dikenal kamus diganti
    kata pada posisi yang sama dari hasil lain bila kata itu dikenal (mis. "ARAMLUNP" -> dari
    hasil lain). Kata yang sudah dikenal tidak pernah diubah."""
    import difflib
    from . import ocrfix
    if not ocrfix.available():
        return main
    tok = re.findall(r"\S+", main)
    core = lambda w: re.sub(r"^[^A-Za-z0-9']+|[^A-Za-z0-9']+$", "", w)
    for other in others:
        ot = re.findall(r"\S+", other)
        a = [core(w).upper() for w in tok]
        bb = [core(w).upper() for w in ot]
        sm = difflib.SequenceMatcher(None, a, bb, autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op != "replace" or (i2 - i1) != (j2 - j1):
                continue
            for k in range(i2 - i1):
                w, alt = core(tok[i1 + k]), core(ot[j1 + k])
                if not w or not alt or ocrfix._known(w.lower()) or not ocrfix._known(alt.lower()):
                    continue
                if difflib.SequenceMatcher(None, w.upper(), alt.upper()).ratio() < 0.6:
                    continue          # terlalu berbeda: bukan kata yang sama yang salah baca
                rep = alt.upper() if w.isupper() else alt
                tok[i1 + k] = tok[i1 + k].replace(w, rep, 1)
    return " ".join(tok)


_OCR_CACHE: dict = {}


def clear_cache():
    _OCR_CACHE.clear()


def ocr_block(img: np.ndarray, b: TextBlock, engine: str, lang: str, gpu: bool = False) -> str:
    crop = _crop(img, b)
    if crop.size == 0:
        return ""
    if engine == "auto":
        engine = "manga-ocr" if lang == "ja" else "easyocr"
    # area yang sama sudah pernah dibaca (OCR ulang, Terjemahkan Semua setelah Deteksi, dst.)
    import hashlib
    key = (hashlib.blake2b(np.ascontiguousarray(crop).data, digest_size=16).hexdigest(), crop.shape,
           engine, lang, str(getattr(b, "_lines", None)), bool(b.vertical))
    hit = _OCR_CACHE.get(key)
    if hit is not None:
        b._ocr_conf = hit[1]
        return hit[0]
    text = _ocr_block(img, b, crop, engine, lang, gpu)
    if len(_OCR_CACHE) > 600:
        _OCR_CACHE.clear()
    _OCR_CACHE[key] = (text, float(getattr(b, "_ocr_conf", 0.0) or 0.0))
    return text


def _dots_text(text: str, img, b) -> str:
    """Blok '1 huruf + titik-titik' ("I...", "A...", "N..."): hasil OCR huruf tunggal sering kacau
    ("Te.", "l..", "|.."). Ambil satu huruf yang paling masuk akal lalu tambahkan '...'."""
    core = re.sub(r"[^A-Za-z0-9|!]", "", text or "")
    if not core:
        return text
    ch = core[0]
    x, y, w, h = b._dots
    if ch in "lI1|!iTtJj":
        # "I" (berkait atas & bawah) vs "T" (bawahnya hanya batang tipis): bandingkan lebar tinta
        # di bagian atas & bawah huruf
        H, W = img.shape[:2]
        g = cv2.cvtColor(img[max(0, y):min(H, y + h), max(0, x):min(W, x + w)], cv2.COLOR_BGR2GRAY)
        if g.size:
            ink = g < 120
            k = max(1, h // 5)
            top = ink[:k].any(axis=0).sum()
            bot = ink[-k:].any(axis=0).sum()
            ch = "I" if (w < 0.45 * h or bot >= 0.55 * max(1, top)) else "T"
    return ch.upper() + "..."


def _ocr_block(img, b, crop, engine, lang, gpu) -> str:

    if engine == "manga-ocr":
        mocr = _get_manga_ocr()
        ang = text_angle(crop) if not b.vertical else 0.0
        pil = Image.fromarray(cv2.cvtColor(deskew(crop, ang) if abs(ang) >= 6 else crop, cv2.COLOR_BGR2RGB))
        text = mocr(pil)
    elif engine == "easyocr":
        from .detector import get_easyocr
        reader = get_easyocr(lang, gpu)
        best = _best_read(reader, img, b, crop, lang)
        text = best[0]
        b._ocr_conf = float(best[1])
    else:
        raise ValueError(f"Engine OCR tidak dikenal: {engine}")
    text = clean_text(text, lang)
    if lang == "en":
        from . import ocrfix
        text = ocrfix.fix(text, lang)
    if getattr(b, "_dots", None) and lang in ("en", "id"):
        text = _dots_text(text, img, b)
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
        text = _tidy_latin(text)
    return text


def _tidy_latin(text: str) -> str:
    """Rapikan teks Latin hasil OCR:
    - kata yang dipotong ke baris berikut ("FOL- LOWING", "SUP- POSE") disambung kembali bila hasil
      sambungannya kata yang dikenal; tanda hubung asli ("HEART- WARMING") tetap tanpa spasi
    - spasi sebelum tanda baca dihapus ("WHAT ?" -> "WHAT?"), apostrof dirapikan ("I ' M" -> "I'M")
    - ".." / ". . ." / "…" -> "..."
    - teks yang hampir semuanya huruf kapital (komik) dijadikan kapital seluruhnya"""
    t = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    t = re.sub(r"\s*'\s*(?=(?:S|M|LL|RE|VE|D|T)\b)", "'", t, flags=re.I)
    t = re.sub(r"\.(?:\s?\.)+|…", "...", t)          # spasi SETELAH titik-tiga tetap ada
    t = re.sub(r"\s+([,.!?;:])", r"\1", t)

    def join(m):
        a, bpart = m.group(1), m.group(2)
        try:
            from . import ocrfix
            if ocrfix.available() and ocrfix._known((a + bpart).lower()):
                return a + bpart
        except Exception:
            pass
        return a + "-" + bpart
    t = re.sub(r"([A-Za-z]{2,})-\s+([A-Za-z]{2,})", join, t)
    letters = [c for c in t if c.isalpha()]
    if len(letters) >= 4 and sum(c.isupper() for c in letters) >= 0.75 * len(letters):
        t = t.upper()
    return t.strip()


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
