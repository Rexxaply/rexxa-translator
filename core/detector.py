"""Deteksi balon kata & area teks.

Dua mode:
- "bubble"  : OpenCV murni (tanpa model, cepat). Mencari area putih tertutup
              (balon) yang berisi piksel gelap (teks).
- "easyocr" : memakai detektor EasyOCR (lebih bagus untuk teks di luar balon),
              kotak-kotak yang berdekatan digabung jadi satu blok.
Hasil kedua mode bisa digabung (mode "hybrid").
"""
from __future__ import annotations

import cv2
import numpy as np

from .models import TextBlock


def load_image(path: str) -> np.ndarray:
    """cv2.imread tidak bisa path unicode di Windows, jadi pakai imdecode."""
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Gagal membuka gambar: {path}")
    return img


def save_image(path: str, img: np.ndarray):
    ext = "." + path.rsplit(".", 1)[-1].lower()
    ok, buf = cv2.imencode(ext if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp") else ".png", img)
    if not ok:
        raise IOError(f"Gagal menyimpan {path}")
    buf.tofile(path)


# ---------------------------------------------------------------- bubble (OpenCV)

def _letter_candidates(gray):
    H, W = gray.shape
    # gelap relatif terhadap latar lokal (tangkap huruf tipis/abu-abu)
    bg = cv2.dilate(gray, np.ones((9, 9), np.uint8))
    dark = ((gray < 170) & (bg.astype(int) - gray > 55)).astype(np.uint8)
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    hmin = max(5, int(H * 0.004))
    hmax = int(H * 0.05)
    light = gray > 190
    mid = (gray > 170) & (gray <= 190) | ((gray >= 60) & (gray <= 170) & (dark == 0))
    out = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if h < hmin or h > hmax or w > hmax * 2.5 or a < 6:
            continue
        fill = a / float(w * h)
        if fill < 0.08 or fill > 0.95:
            continue
        p = max(2, int(h * 0.45))
        x0, y0, x1, y1 = max(0, x - p), max(0, y - p), min(W, x + w + p), min(H, y + h + p)
        comp = (lbl[y0:y1, x0:x1] == i)
        others = ~comp
        tot = others.sum()
        if tot <= 0:
            continue
        lf = (light[y0:y1, x0:x1] & others).sum() / tot
        mf = (mid[y0:y1, x0:x1] & others).sum() / tot
        if lf < 0.45 or mf > 0.35:
            continue
        out.append((int(x), int(y), int(w), int(h)))
    return out


class DSU:
    def __init__(s, n): s.p = list(range(n))
    def f(s, a):
        while s.p[a] != a:
            s.p[a] = s.p[s.p[a]]; a = s.p[a]
        return a
    def u(s, a, b): s.p[s.f(a)] = s.f(b)


def _clusters(items, link):
    d = DSU(len(items))
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if link(items[i], items[j]):
                d.u(i, j)
    out = {}
    for i in range(len(items)):
        out.setdefault(d.f(i), []).append(items[i])
    return list(out.values())


def _bbox(mem):
    x0 = min(c[0] for c in mem); y0 = min(c[1] for c in mem)
    x1 = max(c[0] + c[2] for c in mem); y1 = max(c[1] + c[3] for c in mem)
    return (x0, y0, x1 - x0, y1 - y0)


def _ov(a0, a1, b0, b1):
    return max(0, min(a1, b1) - max(a0, b0))


def _group_letters(cands, shape):
    """Huruf -> baris (horizontal atau vertikal) -> blok."""
    if not cands:
        return []
    cands = sorted(cands, key=lambda c: c[0])

    def link_h(a, b):  # satu baris horizontal
        ha, hb = a[3], b[3]
        if max(ha, hb) > 2.2 * min(ha, hb):
            return False
        if _ov(a[1], a[1] + ha, b[1], b[1] + hb) < 0.5 * min(ha, hb):
            return False
        gap = max(a[0], b[0]) - min(a[0] + a[2], b[0] + b[2])
        return gap < 0.9 * max(ha, hb)

    def link_v(a, b):  # satu kolom vertikal (JP/ZH)
        wa, wb = a[2], b[2]
        sa, sb = max(a[2], a[3]), max(b[2], b[3])
        if max(sa, sb) > 2.2 * min(sa, sb):
            return False
        if _ov(a[0], a[0] + wa, b[0], b[0] + wb) < 0.5 * min(wa, wb):
            return False
        gap = max(a[1], b[1]) - min(a[1] + a[3], b[1] + b[3])
        return gap < 0.6 * max(sa, sb)

    lines = []
    for link, kind in ((link_h, "h"), (link_v, "v")):
        for mem in _clusters(cands, link):
            if len(mem) >= 3 or (len(mem) == 2 and kind == "h"):
                r = _bbox(mem)
                hs = np.array([c[3] for c in mem], float)
                size = float(np.median(hs)) if kind == "h" else float(np.median([max(c[2], c[3]) for c in mem]))
                lines.append(dict(rect=r, n=len(mem), size=size, kind=kind,
                                  cv=float(hs.std() / (hs.mean() or 1)), mem=mem))
    # buang baris yang hampir tertutup baris lain (h vs v ganda)
    lines.sort(key=lambda l: -l["n"])
    keep = []
    for l in lines:
        x, y, w, h = l["rect"]
        if any(_ov(x, x + w, k["rect"][0], k["rect"][0] + k["rect"][2]) *
               _ov(y, y + h, k["rect"][1], k["rect"][1] + k["rect"][3]) > 0.6 * w * h for k in keep):
            continue
        keep.append(l)

    def link_b(a, b):  # baris bertetangga dalam satu blok
        (ax, ay, aw, ah), (bx, by, bw, bh) = a["rect"], b["rect"]
        s = max(a["size"], b["size"])
        if max(a["size"], b["size"]) > 1.8 * min(a["size"], b["size"]):
            return False
        gx = max(ax, bx) - min(ax + aw, bx + bw)
        gy = max(ay, by) - min(ay + ah, by + bh)
        return gx < 0.8 * s and gy < 0.8 * s

    blocks = []
    for mem in _clusters(keep, link_b):
        r = _bbox([l["rect"] for l in mem])
        n = sum(l["n"] for l in mem)
        blocks.append(dict(rect=r, n=n, lines=len(mem), med_h=float(np.median([l["size"] for l in mem])),
                           cv=float(np.mean([l["cv"] for l in mem])),
                           vertical=sum(l["kind"] == "v" for l in mem) > len(mem) / 2))
    return blocks


def _find_bubble(gray, rect, closek):
    """Area putih tertutup yang membungkus kelompok teks."""
    H, W = gray.shape
    x, y, w, h = rect
    white = (gray > 185).astype(np.uint8) * 255
    pad = 3
    white[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad] = 255  # tutup huruf
    white = cv2.erode(white, np.ones((closek, closek), np.uint8))  # putus sambungan tipis
    n, lbl, st, _ = cv2.connectedComponentsWithStats(white, connectivity=4)
    cy, cx = y + h // 2, x + w // 2
    i = lbl[cy, cx]
    if i == 0:
        return None
    bx, by, bw, bh, area = st[i]
    touches = bx <= 1 or by <= 1 or bx + bw >= W - 1 or by + bh >= H - 1
    if touches or area > 14 * w * h or area > 0.2 * H * W:
        return None
    mask = (lbl == i).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((closek, closek), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(cnts, key=cv2.contourArea)
    hull = cv2.convexHull(c)
    return cv2.boundingRect(hull), hull.reshape(-1, 2)


def _ring_light(gray, rect, pad):
    H, W = gray.shape
    x, y, w, h = rect
    x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)
    reg = gray[y0:y1, x0:x1] > 190
    inner = np.zeros_like(reg)
    inner[y - y0:y - y0 + h, x - x0:x - x0 + w] = True
    ring = ~inner
    return reg[ring].mean() if ring.any() else 0


def _grow_light(gray, x0, y0, x1, y1, step, limit):
    """Perluas tiap sisi kotak selama pita barunya masih (hampir) putih."""
    H, W = gray.shape
    ox0, oy0, ox1, oy1 = x0, y0, x1, y1
    grew = True
    while grew:
        grew = False
        for side in ("l", "r", "t", "b"):
            if side == "l" and x0 - step >= 0 and ox0 - (x0 - step) <= limit:
                strip = gray[y0:y1, x0 - step:x0]
            elif side == "r" and x1 + step <= W and (x1 + step) - ox1 <= limit:
                strip = gray[y0:y1, x1:x1 + step]
            elif side == "t" and y0 - step >= 0 and oy0 - (y0 - step) <= limit:
                strip = gray[y0 - step:y0, x0:x1]
            elif side == "b" and y1 + step <= H and (y1 + step) - oy1 <= limit:
                strip = gray[y1:y1 + step, x0:x1]
            else:
                continue
            # >=88% putih: tetap melebar melewati titik-titik/tanda baca kecil,
            # tapi berhenti di garis balon atau gambar
            if strip.size and (strip > 190).mean() > 0.88:
                if side == "l": x0 -= step
                elif side == "r": x1 += step
                elif side == "t": y0 -= step
                else: y1 += step
                grew = True
    # sisakan sedikit jarak dari tepi gambar/garis
    m = step
    if (x0, y0, x1, y1) != (ox0, oy0, ox1, oy1):
        x0, y0 = min(ox0, x0 + m), min(oy0, y0 + m)
        x1, y1 = max(ox1, x1 - m), max(oy1, y1 - m)
    return int(x0), int(y0), int(x1), int(y1)


def detect_bubbles(img: np.ndarray) -> list[TextBlock]:
    """Teks dulu, baru balon:
    1. cari komponen berbentuk huruf yang dikelilingi latar terang,
    2. susun jadi baris (horizontal / vertikal) lalu blok teks,
    3. buang yang bukan teks (bunga, screentone, wajah): tinta tipis atau tinggi huruf tidak seragam,
    4. cari balon tertutup di sekeliling blok; kalau balon terbuka -> kotak teks bebas.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    groups = _group_letters(_letter_candidates(gray), gray.shape)
    closek = max(3, int(min(H, W) * 0.004)) | 1
    blocks: list[TextBlock] = []
    for g in groups:
        x, y, w, h = g["rect"]
        if g["n"] < 4 or g["cv"] > 0.3:
            continue
        if (gray[y:y + h, x:x + w] < 120).mean() < 0.12:
            continue
        ring = _ring_light(gray, g["rect"], int(g["med_h"] * 0.8))
        if ring < 0.5:          # teks putih di atas gambar gelap -> lewati (pakai mode hybrid)
            continue
        b = _find_bubble(gray, g["rect"], closek)
        if b is not None:
            (bx, by, bw, bh), hull = b
            blocks.append(TextBlock(x=int(bx), y=int(by), w=int(bw), h=int(bh), kind="bubble",
                                    vertical=bool(g["vertical"]),
                                    mask_poly=hull.astype(int).tolist()))
        elif ring > 0.75:
            # balon terbuka / tanpa garis: lebarkan kotak ke area putih di sekitarnya
            x0, y0, x1, y1 = _grow_light(gray, x, y, x + w, y + h, step=max(2, int(g["med_h"] * 0.25)),
                                         limit=int(g["med_h"] * 3))
            blocks.append(TextBlock(x=x0, y=y0, w=x1 - x0, h=y1 - y0, kind="free",
                                    vertical=bool(g["vertical"])))
    return _dedupe(blocks)


def _dedupe(blocks: list[TextBlock]) -> list[TextBlock]:
    """Buang kotak yang hampir seluruhnya berada di dalam kotak lain."""
    blocks = sorted(blocks, key=lambda b: b.w * b.h, reverse=True)
    keep: list[TextBlock] = []
    for b in blocks:
        inside = False
        for k in keep:
            ix = max(0, min(b.x + b.w, k.x + k.w) - max(b.x, k.x))
            iy = max(0, min(b.y + b.h, k.y + k.h) - max(b.y, k.y))
            if ix * iy > 0.8 * b.w * b.h:
                inside = True
                break
        if not inside:
            keep.append(b)
    return keep


# ---------------------------------------------------------------- EasyOCR detector

_easy_readers: dict = {}


def get_easyocr(lang: str, gpu: bool):
    import easyocr  # import berat, hanya saat dipakai
    langs = {"ja": ["ja", "en"], "zh": ["ch_sim", "en"], "zh-tw": ["ch_tra", "en"],
             "ko": ["ko", "en"]}.get(lang, ["en"])
    key = (tuple(langs), gpu)
    if key not in _easy_readers:
        _easy_readers[key] = easyocr.Reader(langs, gpu=gpu)
    return _easy_readers[key]


def detect_text_easyocr(img: np.ndarray, lang: str, gpu: bool = False) -> list[TextBlock]:
    reader = get_easyocr(lang, gpu)
    horiz, free = reader.detect(img, min_size=10, text_threshold=0.6, link_threshold=0.4)
    rects = []
    for x0, x1, y0, y1 in horiz[0]:
        rects.append([int(x0), int(y0), int(x1 - x0), int(y1 - y0)])
    for poly in free[0]:
        pts = np.array(poly, dtype=np.int32)
        rects.append(list(cv2.boundingRect(pts)))
    merged = _merge_close(rects, gap=max(8, img.shape[0] // 150))
    return [TextBlock(x=int(r[0]), y=int(r[1]), w=int(r[2]), h=int(r[3]), kind="free",
                      vertical=bool(r[3] > r[2] * 1.3))
            for r in merged if r[2] > 5 and r[3] > 5]


def _merge_close(rects, gap):
    changed = True
    rects = [r[:] for r in rects]
    while changed:
        changed = False
        out = []
        while rects:
            a = rects.pop()
            i = 0
            while i < len(rects):
                b = rects[i]
                if (a[0] - gap < b[0] + b[2] and b[0] - gap < a[0] + a[2] and
                        a[1] - gap < b[1] + b[3] and b[1] - gap < a[1] + a[3]):
                    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
                    x1, y1 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
                    a = [x0, y0, x1 - x0, y1 - y0]
                    rects.pop(i)
                    changed = True
                else:
                    i += 1
            out.append(a)
        rects = out
    return rects


# ---------------------------------------------------------------- API utama

def detect(img: np.ndarray, mode: str = "bubble", lang: str = "ja", gpu: bool = False) -> list[TextBlock]:
    if mode == "bubble":
        blocks = detect_bubbles(img)
    elif mode == "easyocr":
        blocks = detect_text_easyocr(img, lang, gpu)
    elif mode == "hybrid":
        bubbles = detect_bubbles(img)
        try:
            extra = detect_text_easyocr(img, lang, gpu)
        except ImportError:
            extra = []
        for e in extra:  # tambah teks yang tidak berada di dalam balon
            cx, cy = e.x + e.w / 2, e.y + e.h / 2
            if not any(b.x <= cx <= b.x + b.w and b.y <= cy <= b.y + b.h for b in bubbles):
                bubbles.append(e)
        blocks = bubbles
    else:
        raise ValueError(f"Mode deteksi tidak dikenal: {mode}")
    return sort_reading_order(blocks, rtl=lang in ("ja", "zh", "zh-tw"))


def sort_reading_order(blocks: list[TextBlock], rtl: bool) -> list[TextBlock]:
    """Urutan baca: baris atas dulu; dalam satu baris kanan->kiri (manga) atau kiri->kanan."""
    if not blocks:
        return blocks
    blocks = sorted(blocks, key=lambda b: b.y)
    rows, cur = [], [blocks[0]]
    for b in blocks[1:]:
        ref = cur[0]
        if b.y < ref.y + ref.h * 0.5:
            cur.append(b)
        else:
            rows.append(cur)
            cur = [b]
    rows.append(cur)
    out = []
    for r in rows:
        out += sorted(r, key=lambda b: b.x + b.w / 2, reverse=rtl)
    return out
