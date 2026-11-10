"""Teks spesial / SFX besar (mis. "GET AWAY FROM HER!!" dengan huruf kuas tebal).

Huruf dialog biasa dideteksi di detector.py. Huruf SFX jauh lebih besar, sering miring,
saling menempel, dan menyentuh garis balon, jadi dicari dengan cara lain: goresan TEBAL
(garis gambar, rambut tipis, dan screentone hilang saat dibuka dengan kernel bulat),
lalu dikelompokkan menjadi kata/baris."""
from __future__ import annotations

import cv2
import numpy as np

from .models import TextBlock


def _ref(shape):
    H, W = shape[:2]
    return float(min(H, W * 1.45))


def _thick(gray, ref):
    dark = (gray < 100).astype(np.uint8)
    r = max(2, int(round(ref * 0.0028)))          # goresan > ~2r px
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    return dark, cv2.morphologyEx(dark, cv2.MORPH_OPEN, k), r


def _letters(gray, with_labels=False):
    H, W = gray.shape
    ref = _ref(gray.shape)
    dark, thick, r = _thick(gray, ref)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(thick, connectivity=8)
    hmin, hmax = ref * 0.035, ref * 0.17
    light = gray > 185
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if not (hmin <= h <= hmax) or w > 2.6 * h or w < 0.15 * h:
            continue
        fill = a / float(w * h)
        if not (0.18 <= fill <= 0.8):
            continue
        p = max(3, int(h * 0.25))
        x0, y0, x1, y1 = max(0, x - p), max(0, y - p), min(W, x + w + p), min(H, y + h + p)
        comp = lbl[y0:y1, x0:x1] == i
        ring = ~cv2.dilate(comp.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        if not ring.any():
            continue
        lf = (light[y0:y1, x0:x1] & ring).sum() / ring.sum()
        if lf < 0.4:            # huruf SFX berada di latar terang (balon / garis tepi putih)
            continue
        out.append((int(x), int(y), int(w), int(h), i) if with_labels else (int(x), int(y), int(w), int(h)))
    if with_labels:
        return out, lbl, dark, r
    return out


def detect_sfx(img: np.ndarray, existing: list[TextBlock]) -> list[TextBlock]:
    from .detector import _clusters, _bbox
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cands = _letters(gray)
    if len(cands) < 3:
        return []

    def link(a, b):
        ha, hb = a[3], b[3]
        if max(ha, hb) > 1.7 * min(ha, hb):
            return False
        s = max(ha, hb)
        gx = max(a[0], b[0]) - min(a[0] + a[2], b[0] + b[2])
        gy = max(a[1], b[1]) - min(a[1] + a[3], b[1] + b[3])
        return gx < 0.45 * s and gy < 0.45 * s

    out = []
    for mem in _clusters(cands, link):
        if len(mem) < 4:
            continue
        hs = np.array([c[3] for c in mem], float)
        if hs.std() / hs.mean() > 0.35:
            continue
        x, y, w, h = _bbox(mem)
        # bentuk tulisan: huruf tidak terlalu ramping (helai rambut), tersusun dalam baris,
        # dan cukup mengisi area tulisannya
        if np.median([c[2] / c[3] for c in mem]) < 0.38:
            continue
        rows = _rows(mem)
        if max(len(r) for r in rows) < 3 or sum(len(r) for r in rows if len(r) >= 2) < 0.7 * len(mem):
            continue
        if sum(c[2] * c[3] for c in mem) < 0.25 * w * h:
            continue
        # bukan teks yang sudah terdeteksi
        if any(_overlap((x, y, w, h), (b.x, b.y, b.w, b.h)) > 0.3 for b in existing):
            continue
        med = float(np.median(hs))
        pad = int(med * 0.15)
        H, W = gray.shape
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(W, x + w + pad), min(H, y + h + pad)
        out.append(TextBlock(x=x0, y=y0, w=x1 - x0, h=y1 - y0, kind="free", sfx=True,
                             text_rect=[int(x), int(y), int(w), int(h)], src_h=int(round(med)),
                             rotation=_tilt(mem)))
    return out


def _rows(mem):
    mem = sorted(mem, key=lambda c: c[1] + c[3] / 2)
    rows, cur = [], [mem[0]]
    for c in mem[1:]:
        ref = cur[-1]
        if abs((c[1] + c[3] / 2) - (ref[1] + ref[3] / 2)) < 0.45 * max(c[3], ref[3]):
            cur.append(c)
        else:
            rows.append(cur)
            cur = [c]
    rows.append(cur)
    return rows


def _tilt(mem) -> float:
    """Kemiringan baris SFX (derajat, untuk diputar sama seperti aslinya)."""
    rows = _rows(mem)
    angles = []
    for r in rows:
        if len(r) >= 2:
            xs = np.array([c[0] + c[2] / 2 for c in r], float)
            ys = np.array([c[1] + c[3] / 2 for c in r], float)
            if np.ptp(xs) > 0:
                angles.append(np.degrees(np.arctan(np.polyfit(xs, ys, 1)[0])))
    if not angles:
        return 0.0
    a = float(np.median(angles))
    return round(-a, 1) if 3 <= abs(a) <= 30 else 0.0


def _overlap(a, b):
    ix = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    return ix * iy / float(max(1, min(a[2] * a[3], b[2] * b[3])))


def sfx_mask(img: np.ndarray, b: TextBlock) -> np.ndarray | None:
    """Piksel huruf SFX saja (goresan tebal yang dikenali sebagai huruf + tepinya),
    TANPA garis balon, rambut, atau gambar di sekitarnya."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    x, y, w, h = b.text_rect if b.text_rect else (b.x, b.y, b.w, b.h)
    cands, lbl, dark, r = _letters(gray, with_labels=True)
    ids = [c[4] for c in cands
           if x - 2 <= c[0] + c[2] / 2 <= x + w + 2 and y - 2 <= c[1] + c[3] / 2 <= y + h + 2]
    if not ids:
        return None
    # goresan tebal lain yang seluruhnya berada di area teks (huruf "O", palang "T"/"E", "!!")
    sh = float(b.src_h or h)
    pad = sh * 0.2
    n = int(lbl.max()) + 1
    if n > 1:
        ys, xs = np.nonzero(lbl)
        sub = lbl[ys, xs]
        x0s = np.full(n, 1e9); y0s = np.full(n, 1e9); x1s = np.full(n, -1.0); y1s = np.full(n, -1.0)
        np.minimum.at(x0s, sub, xs); np.minimum.at(y0s, sub, ys)
        np.maximum.at(x1s, sub, xs); np.maximum.at(y1s, sub, ys)
        for i in range(1, n):
            if (x0s[i] >= x - pad and y0s[i] >= y - pad and x1s[i] <= x + w + pad and y1s[i] <= y + h + pad
                    and y1s[i] - y0s[i] <= sh * 1.9):
                ids.append(i)
    core = np.isin(lbl, ids).astype(np.uint8)
    # kembalikan tepi goresan yang terkikis + bagian tipis huruf (dibatasi piksel gelap asli)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 7, 2 * r + 7))
    letters = cv2.dilate(core, k) & dark
    zone = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(sh * 0.35) | 1,) * 2))
    # serpihan gelap kecil di dalam area teks (titik "!", ujung goresan kuas yang terpisah)
    X0, Y0 = int(max(0, x - pad)), int(max(0, y - pad))
    X1, Y1 = int(min(W, x + w + pad)), int(min(H, y + h + pad))
    sub = dark[Y0:Y1, X0:X1]
    n2, l2, st2, _ = cv2.connectedComponentsWithStats(sub, connectivity=8)
    small = np.zeros(n2, bool)
    for i in range(1, n2):
        cx, cy, cw, ch, _a = st2[i]
        inside = cx > 0 and cy > 0 and cx + cw < sub.shape[1] and cy + ch < sub.shape[0]
        if inside and max(cw, ch) <= sh * 0.6:
            small[i] = True
    # hanya serpihan di dekat huruf (bukan titik-titik screentone di rambut)
    letters[Y0:Y1, X0:X1] |= small[l2].astype(np.uint8) & zone[Y0:Y1, X0:X1]
    letters = cv2.dilate(letters * 255, np.ones((3, 3), np.uint8), iterations=2)
    return letters
