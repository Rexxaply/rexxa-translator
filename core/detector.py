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

def _ref_size(shape) -> float:
    """Ukuran acuan halaman. Manga: tinggi halaman. Webtoon (strip panjang manhwa/manhua):
    tinggi gambar bisa 20x lebarnya, jadi ukuran huruf diukur dari lebar, bukan tinggi."""
    H, W = shape[:2]
    return float(min(H, W * 1.45))


def _letter_candidates(gray, weak=False):
    H, W = gray.shape
    # gelap relatif terhadap latar lokal (tangkap huruf tipis/abu-abu)
    bg = cv2.dilate(gray, np.ones((9, 9), np.uint8))
    dark = ((gray < 170) & (bg.astype(int) - gray > 55)).astype(np.uint8)
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    ref = _ref_size(gray.shape)
    hmin = max(6, int(ref * 0.005))
    hmax = int(ref * 0.05)
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
        if weak:
            # huruf di pita abu-abu balon transparan: hanya dipakai untuk MEMPERPANJANG baris yang sudah ada
            if lf + mf < 0.6:
                continue
        elif lf < 0.45 or mf > 0.35:
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


def _clusters(items, link, rect=lambda it: it):
    """Gabungkan item yang saling 'link'. Hanya membandingkan item yang berdekatan (grid spasial),
    jadi tetap cepat walau ada ribuan kandidat dari screentone."""
    n = len(items)
    d = DSU(n)
    if n == 0:
        return []
    rects = [rect(it) for it in items]
    cell = max(8, int(np.median([max(r[2], r[3]) for r in rects]) * 3))
    grid = {}
    for i, (x, y, w, h) in enumerate(rects):
        for gx in range(x // cell, (x + w) // cell + 1):
            for gy in range(y // cell, (y + h) // cell + 1):
                grid.setdefault((gx, gy), []).append(i)
    seen = set()
    for i, (x, y, w, h) in enumerate(rects):
        for gx in range(x // cell - 1, (x + w) // cell + 2):
            for gy in range(y // cell - 1, (y + h) // cell + 2):
                for j in grid.get((gx, gy), ()):
                    if j <= i or (i, j) in seen:
                        continue
                    seen.add((i, j))
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


def _group_letters(cands, shape, allow_v: bool = True):
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
    for link, kind in ((link_h, "h"), (link_v, "v")) if allow_v else ((link_h, "h"),):
        for mem in _clusters(cands, link):  # noqa: B023
            if len(mem) >= 3 or (len(mem) == 2 and kind == "h"):
                r = _bbox(mem)
                hs = np.array([c[3] for c in mem], float)
                size = float(np.median(hs)) if kind == "h" else float(np.median([max(c[2], c[3]) for c in mem]))
                if kind == "v" and r[2] > 1.8 * size:
                    continue    # "kolom" selebar beberapa huruf = baris-baris teks horizontal yang bertumpuk
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
        if gx < 0.8 * s and gy < 0.8 * s:
            return True
        # teks rata tengah dengan satu baris pendek yang tak terbaca di antaranya ("AS" yang hurufnya menempel)
        acx, bcx = ax + aw / 2, bx + bw / 2
        return (a["n"] >= 3 and b["n"] >= 3 and gx < 0 and gy < 1.6 * s
                and abs(acx - bcx) < 0.25 * max(aw, bw) + 0.5 * s)

    blocks = []
    for mem in _clusters(keep, link_b, rect=lambda l: l["rect"]):
        r = _bbox([l["rect"] for l in mem])
        n = sum(l["n"] for l in mem)
        blocks.append(_block_from_lines(mem))
    return blocks


def _block_from_lines(mem):
    return dict(rect=_bbox([l["rect"] for l in mem]), n=sum(l["n"] for l in mem), lines=len(mem),
                med_h=float(np.median([l["size"] for l in mem])),
                cv=float(np.mean([l["cv"] for l in mem])),
                vertical=sum(l["kind"] == "v" for l in mem) > len(mem) / 2,
                line_list=mem)


def _absorb_single(groups, cands):
    """Baris yang hurufnya menempel jadi SATU komponen ("OUT", "AS") tidak membentuk baris sendiri.
    Masukkan ke blok di atas/bawahnya bila tingginya sama dan posisinya di dalam lebar blok."""
    used = {c for g in groups for l in g["line_list"] for c in l["mem"]}
    free = [c for c in cands if c not in used]
    if not free:
        return groups
    out = []
    for g in groups:
        if g["vertical"] or g["n"] < 4:
            out.append(g)
            continue
        lines = list(g["line_list"])
        s = g["med_h"]
        x0, y0, w, h = g["rect"]
        added = True
        while added:
            added = False
            for c in free:
                cx, cy, cw, ch = c
                if any(c in l["mem"] for l in lines) or not (0.75 * s <= ch <= 1.35 * s):
                    continue
                if not (x0 <= cx + cw / 2 <= x0 + w) or cw > w:
                    continue
                gy = max(y0, cy) - min(y0 + h, cy + ch)
                if 0 <= gy < 0.8 * s:
                    lines.append(dict(rect=c, n=1, size=float(ch), kind="h", cv=0.0, mem=[c]))
                    y0, y1 = min(y0, cy), max(y0 + h, cy + ch)
                    h = y1 - y0
                    added = True
        out.append(_block_from_lines(lines) if len(lines) != len(g["line_list"]) else g)
    return out


def _extend_lines(groups, weak):
    """Huruf di ujung baris yang latarnya abu-abu (balon transparan di atas gambar) sering lolos dari
    deteksi ketat. Tambahkan ke baris bila tingginya sama, sejajar, dan menempel di ujung baris."""
    if not weak:
        return groups
    out = []
    for g in groups:
        lines = []
        changed_any = False
        for l in g["line_list"]:
            if l["kind"] != "h":
                lines.append(l)
                continue
            mem = list(l["mem"])
            x0, y0, w, h = l["rect"]
            x1, y1 = x0 + w, y0 + h
            s = l["size"]
            grow = True
            while grow:
                grow = False
                for c in weak:
                    cx, cy, cw, ch = c
                    if c in mem or not (0.65 * s <= ch <= 1.5 * s):
                        continue
                    if _ov(y0, y1, cy, cy + ch) < 0.6 * min(ch, y1 - y0):
                        continue
                    gap = max(x0, cx) - min(x1, cx + cw)
                    if gap < 0.9 * s and (cx + cw <= x0 + 2 or cx >= x1 - 2):
                        mem.append(c)
                        x0, x1 = min(x0, cx), max(x1, cx + cw)
                        y0, y1 = min(y0, cy), max(y1, cy + ch)
                        grow = changed_any = True
            if len(mem) != len(l["mem"]):
                hs = np.array([c[3] for c in mem], float)
                l = dict(l, rect=_bbox(mem), n=len(mem), mem=mem, cv=float(hs.std() / (hs.mean() or 1)))
            lines.append(l)
        out.append(_block_from_lines(lines) if changed_any else g)
    return out


def _white_regions(gray, groups, closek):
    """Peta area putih per halaman. Yang ditutup putih hanya kotak tiap BARIS (bukan kotak
    seluruh blok), supaya garis pemisah antara dua balon yang menempel tetap utuh."""
    white = (gray > 185).astype(np.uint8) * 255
    for g in groups:
        for l in g["line_list"]:
            x, y, w, h = l["rect"]
            white[max(0, y - 2):y + h + 2, max(0, x - 2):x + w + 2] = 255
    white = cv2.erode(white, np.ones((closek, closek), np.uint8))
    return cv2.connectedComponentsWithStats(white, connectivity=4)


def _line_region(lbl, rect):
    """Label area putih yang paling banyak ditempati sebuah baris."""
    x, y, w, h = rect
    vals = lbl[y:y + h, x:x + w].ravel()
    vals = vals[vals > 0]
    if vals.size == 0:
        return 0
    return int(np.bincount(vals).argmax())


def _split_by_bubble(g, lbl, stats, shape):
    """Pecah blok bila baris-barisnya berada di balon (area putih tertutup) yang berbeda,
    mis. dua balon yang saling menempel: "RIGHT..." | "SOMETHING LIKE THIS"."""
    H, W = shape
    lines = g["line_list"]
    if len(lines) < 2:
        return [g]
    by_region = {}
    for l in lines:
        r = _line_region(lbl, l["rect"])
        if r == 0:
            return [g]
        bx, by, bw, bh, area = stats[r]
        if bx <= 1 or by <= 1 or bx + bw >= W - 1 or by + bh >= H - 1 or area > 0.2 * _ref_size(shape) * W:
            return [g]          # bukan balon tertutup -> jangan dipecah
        by_region.setdefault(r, []).append(l)
    if len(by_region) < 2:
        return [g]
    return [_block_from_lines(mem) for mem in by_region.values()]


def _find_bubble(gray, rect, closek, line_rects=None):
    """Area putih tertutup yang membungkus kelompok teks."""
    H, W = gray.shape
    x, y, w, h = rect
    white = (gray > 185).astype(np.uint8) * 255
    pad = 3
    for lx, ly, lw, lh in line_rects or [rect]:  # tutup huruf per baris (jangan tembus garis balon)
        white[max(0, ly - pad):ly + lh + pad, max(0, lx - pad):lx + lw + pad] = 255
    white = cv2.erode(white, np.ones((closek, closek), np.uint8))  # putus sambungan tipis
    n, lbl, st, _ = cv2.connectedComponentsWithStats(white, connectivity=4)
    cy, cx = y + h // 2, x + w // 2
    i = lbl[cy, cx]
    if i == 0:
        return None
    bx, by, bw, bh, area = st[i]
    touches = bx <= 1 or by <= 1 or bx + bw >= W - 1 or by + bh >= H - 1
    if touches or area > 14 * w * h or area > 0.2 * _ref_size(gray.shape) * W:
        return None
    mask = (lbl == i).astype(np.uint8) * 255
    if not _text_centered(mask[by:by + bh, bx:bx + bw], (x - bx, y - by, w, h)):
        return None     # area putih panel/langit yang kebetulan tertutup, bukan balon
    mask = cv2.dilate(mask, np.ones((closek, closek), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(cnts, key=cv2.contourArea)
    hull = cv2.convexHull(c)
    return cv2.boundingRect(hull), hull.reshape(-1, 2)


def _text_centered(region, trect) -> bool:
    """Teks di balon selalu berada di tengah balon. Narasi di pojok panel putih / langit
    juga tampak 'tertutup', tapi teksnya menempel di satu sisi -> bukan balon."""
    rh, rw = region.shape
    tx, ty, tw, th = trect
    tcx, tcy = tx + tw / 2, ty + th / 2
    if abs(tcx - rw / 2) > 0.24 * rw or abs(tcy - rh / 2) > 0.24 * rh:
        return False
    dist = cv2.distanceTransform((region > 0).astype(np.uint8), cv2.DIST_L2, 5)
    py, px = np.unravel_index(int(np.argmax(dist)), dist.shape)
    return abs(px - tcx) <= tw / 2 + 0.15 * rw and abs(py - tcy) <= th / 2 + 0.15 * rh


def _region_of(g, lbl):
    votes = [r for r in (_line_region(lbl, l["rect"]) for l in g["line_list"]) if r]
    return max(set(votes), key=votes.count) if votes else 0


def _split_region(lbl, region, groups, closek):
    """Satu area putih berisi beberapa kelompok teks (balon-balon yang menyatu tanpa garis pemisah).
    Cari "leher" di antara lobus balon: bagian dalam area dikikis bertahap (ambang peta jarak naik)
    sampai tiap kelompok teks berada di inti yang terpisah; lalu tiap inti ditumbuhkan kembali
    sampai bertemu — batasnya jatuh tepat di bagian yang menyempit.
    Mengembalikan [(rect, hull) | None] sesuai urutan groups (None = tidak bisa dibelah)."""
    ys, xs = np.nonzero(lbl == region)
    H, W = lbl.shape
    pad = closek * 2
    x0, y0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
    x1, y1 = min(W, xs.max() + 1 + pad), min(H, ys.max() + 1 + pad)
    mask = (lbl[y0:y1, x0:x1] == region).astype(np.uint8)
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)

    def text_px(g):
        out = []
        for lx, ly, lw, lh in (l["rect"] for l in g["line_list"]):
            out.append((slice(max(0, ly - y0), ly - y0 + lh), slice(max(0, lx - x0), lx - x0 + lw)))
        return out

    tps = [text_px(g) for g in groups]
    dmax = float(dist.max())
    cores = None
    for frac in np.linspace(0.15, 0.85, 15):
        n, core = cv2.connectedComponents((dist > dmax * frac).astype(np.uint8))
        owner = []
        for tp in tps:
            vals = np.concatenate([core[sy, sx].ravel() for sy, sx in tp])
            vals = vals[vals > 0]
            owner.append(int(np.bincount(vals).argmax()) if vals.size else 0)
        if all(owner) and len(set(owner)) == len(owner):
            cores = (core, owner)
            break
    if cores is None:
        return [None] * len(groups)

    core, owner = cores
    # tumbuhkan inti dengan kecepatan sama (BFS lewat watershed di atas gambar datar)
    markers = np.zeros(mask.shape, np.int32)
    markers[mask == 0] = 1
    for k, o in enumerate(owner):
        markers[core == o] = k + 2
    cv2.watershed(np.zeros(mask.shape + (3,), np.uint8), markers)
    out = []
    for k in range(len(groups)):
        part = (markers == k + 2).astype(np.uint8) * 255
        part = cv2.dilate(part, np.ones((closek, closek), np.uint8))
        cnts, _ = cv2.findContours(part, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            out.append(None)
            continue
        c = max(cnts, key=cv2.contourArea) + np.array([[[x0, y0]]])
        hull = cv2.convexHull(c)
        out.append((cv2.boundingRect(hull), hull.reshape(-1, 2)))
    return out


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


def detect_bubbles(img: np.ndarray, vertical: bool = True) -> list[TextBlock]:
    """Teks dulu, baru balon:
    1. cari komponen berbentuk huruf yang dikelilingi latar terang,
    2. susun jadi baris (horizontal / vertikal) lalu blok teks,
    3. buang yang bukan teks (bunga, screentone, wajah): tinta tipis atau tinggi huruf tidak seragam,
    4. cari balon tertutup di sekeliling blok; kalau balon terbuka -> kotak teks bebas.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    strong = _letter_candidates(gray)
    groups = _group_letters(strong, gray.shape, allow_v=vertical)   # huruf latin: selalu baris mendatar
    groups = _absorb_single(groups, strong)
    groups = _extend_lines(groups, list(set(_letter_candidates(gray, weak=True)) - set(strong)))
    closek = max(3, int(min(_ref_size(gray.shape), W) * 0.004)) | 1
    _, lbl, stats, _ = _white_regions(gray, groups, closek)
    split = []
    for g in groups:
        split += _split_by_bubble(g, lbl, stats, gray.shape)
    good = []
    for g in split:
        x, y, w, h = g["rect"]
        # huruf campuran besar-kecil ("A good luck kiss!") punya tinggi lebih beragam
        cv_max = 0.42 if g["n"] >= 8 else 0.3
        if g["n"] < 2 or g["cv"] > cv_max:
            continue
        if (gray[y:y + h, x:x + w] < 120).mean() < 0.12:
            continue
        g["ring"] = _ring_light(gray, g["rect"], int(g["med_h"] * 0.8))
        if g["ring"] < 0.5:     # teks putih di atas gambar gelap -> lewati (pakai mode hybrid)
            continue
        if g["n"] < 10 and g["ring"] < 0.65:   # sedikit "huruf" di latar ramai -> garis gambar
            continue
        good.append(g)

    # balon yang menyatu: beberapa kelompok teks di SATU area putih tertutup -> belah per kelompok
    shared = {}
    for g in good:
        r = _region_of(g, lbl)
        if r:
            bx, by, bw, bh, area = stats[r]
            closed = not (bx <= 1 or by <= 1 or bx + bw >= W - 1 or by + bh >= H - 1) and area <= 0.2 * _ref_size(gray.shape) * W
            if closed:
                shared.setdefault(r, []).append(g)
    lobes = {}
    for r, gs in shared.items():
        if len(gs) >= 2:
            for g, res in zip(gs, _split_region(lbl, r, gs, closek)):
                lobes[id(g)] = res

    blocks: list[TextBlock] = []
    for g in good:
        x, y, w, h = g["rect"]
        ring = g["ring"]
        text_rect = [int(v) for v in g["rect"]]
        if id(g) in lobes:
            b = lobes[id(g)]          # None = gagal dibelah -> diperlakukan sebagai teks bebas
        else:
            b = _find_bubble(gray, g["rect"], closek, [l["rect"] for l in g["line_list"]])
        x, y, w, h = g["rect"]
        if g["n"] < 3 and (ring < (0.9 if b is not None else 0.97)
                           or (gray[y:y + h, x:x + w] < 120).mean() < 0.3):
            continue                  # 2 huruf ("OH.") hanya diterima bila latarnya bersih
        if b is not None:
            (bx, by, bw, bh), hull = b
            blocks.append(TextBlock(x=int(bx), y=int(by), w=int(bw), h=int(bh), kind="bubble",
                                    vertical=bool(g["vertical"]), text_rect=text_rect,
                                    src_h=int(round(g["med_h"])), mask_poly=hull.astype(int).tolist()))
        elif ring > 0.75:
            # balon terbuka / tanpa garis: lebarkan kotak ke area putih di sekitarnya
            x0, y0, x1, y1 = _grow_light(gray, x, y, x + w, y + h, step=max(2, int(g["med_h"] * 0.25)),
                                         limit=int(g["med_h"] * 3))
            blocks.append(TextBlock(x=x0, y=y0, w=x1 - x0, h=y1 - y0, kind="free",
                                    vertical=bool(g["vertical"]), text_rect=text_rect,
                                    src_h=int(round(g["med_h"]))))
    # teks bebas yang hurufnya jauh lebih besar dari teks dialog = SFX -> biarkan
    sizes = [b.src_h for b in blocks if b.kind == "bubble" and b.src_h]
    if len(sizes) >= 2:
        med = float(np.median(sizes))
        blocks = [b for b in blocks if not (b.kind == "free" and b.src_h > 2.2 * med)]
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

def _upscale_factor(img) -> int:
    """Gambar kecil / webtoon resolusi rendah (lebar < 700 px): huruf hanya beberapa piksel,
    jadi deteksi dijalankan di gambar yang diperbesar 2x."""
    h, w = img.shape[:2]
    return 2 if w < 700 and h * w * 4 <= 60_000_000 else 1


def _scale_block(b: TextBlock, f: float) -> TextBlock:
    b.x, b.y, b.w, b.h = (int(round(v * f)) for v in (b.x, b.y, b.w, b.h))
    if b.text_rect:
        b.text_rect = [int(round(v * f)) for v in b.text_rect]
    if b.mask_poly:
        b.mask_poly = [[int(round(px * f)), int(round(py * f))] for px, py in b.mask_poly]
    b.src_h = int(round(b.src_h * f))
    return b


def detect(img: np.ndarray, mode: str = "bubble", lang: str = "ja", gpu: bool = False) -> list[TextBlock]:
    k = _upscale_factor(img) if mode in ("bubble", "hybrid") else 1
    if k > 1:
        big = cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
        blocks = _detect(big, mode, lang, gpu)
        return [_scale_block(b, 1.0 / k) for b in blocks]
    return _detect(img, mode, lang, gpu)


def _detect(img: np.ndarray, mode: str, lang: str, gpu: bool) -> list[TextBlock]:
    cjk = lang in ("ja", "zh", "zh-tw", "ko")
    if mode == "bubble":
        blocks = detect_bubbles(img, vertical=cjk)
    elif mode == "easyocr":
        blocks = detect_text_easyocr(img, lang, gpu)
    elif mode == "hybrid":
        bubbles = detect_bubbles(img, vertical=cjk)
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
    if not cjk:
        for b in blocks:
            b.vertical = False
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
