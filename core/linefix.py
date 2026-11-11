"""Sambung ulang garis balon / garis gambar yang terputus setelah teks dihapus -- seperti orang yang
memakai Pen Tool + alat garis:

1. Cari UJUNG garis yang berhenti tepat di area yang baru dibersihkan (garis yang 'kepotong').
2. Baca arah garis di ujungnya (beberapa belas piksel terakhir), tebalnya, dan warnanya.
3. Pasangkan dua ujung yang saling menghadap (arahnya segaris, jaraknya masuk akal, celahnya
   memang berada di area yang dibersihkan -- bukan celah yang memang ada di gambar).
4. Gambar kurva halus (Bezier: titik jangkar di kedua ujung, pegangan mengikuti arah garis)
   dengan tebal & warna yang sama, antialias.
"""
from __future__ import annotations

import cv2
import numpy as np


def _thin(mask: np.ndarray, max_iter: int = 40) -> np.ndarray:
    """Penipisan Zhang-Suen (garis jadi 1 piksel)."""
    img = (mask > 0).astype(np.uint8)
    img = np.pad(img, 1)
    for _ in range(max_iter):
        changed = False
        for step in (0, 1):
            P = img
            p2, p3, p4 = P[:-2, 1:-1], P[:-2, 2:], P[1:-1, 2:]
            p5, p6, p7 = P[2:, 2:], P[2:, 1:-1], P[2:, :-2]
            p8, p9 = P[1:-1, :-2], P[:-2, :-2]
            c = P[1:-1, 1:-1]
            nb = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            trans = sum(((seq[k] == 0) & (seq[k + 1] == 1)).astype(np.uint8) for k in range(8))
            if step == 0:
                cond = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                cond = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            rm = (c == 1) & (nb >= 2) & (nb <= 6) & (trans == 1) & cond
            if rm.any():
                img[1:-1, 1:-1][rm] = 0
                changed = True
        if not changed:
            break
    return img[1:-1, 1:-1].astype(bool)


_NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _endpoints(sk: np.ndarray):
    k = np.ones((3, 3), np.uint8)
    k[1, 1] = 0
    n = cv2.filter2D(sk.astype(np.uint8), -1, k, borderType=cv2.BORDER_CONSTANT)
    ys, xs = np.nonzero(sk & (n == 1))
    return list(zip(ys.tolist(), xs.tolist()))


def _trace(sk: np.ndarray, y: int, x: int, n: int = 18):
    """Jalan dari ujung ke dalam garis sejauh n piksel. Berhenti di percabangan."""
    H, W = sk.shape
    path = [(y, x)]
    seen = {(y, x)}
    cy, cx = y, x
    for _ in range(n):
        nxt = [(cy + dy, cx + dx) for dy, dx in _NB
               if 0 <= cy + dy < H and 0 <= cx + dx < W and sk[cy + dy, cx + dx] and (cy + dy, cx + dx) not in seen]
        if len(nxt) != 1:
            if len(nxt) == 0:
                break
            # sedikit cabang (piksel bertetangga) masih boleh: ambil yang melanjutkan arah
            if len(path) >= 2:
                py, px = path[-2]
                nxt.sort(key=lambda p: -((p[0] - cy) * (cy - py) + (p[1] - cx) * (cx - px)))
            nxt = nxt[:1]
        cy, cx = nxt[0]
        seen.add((cy, cx))
        path.append((cy, cx))
    return path


def _bezier(p0, p1, p2, p3, n):
    t = np.linspace(0, 1, n)[:, None]
    return ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t * t * p2 + (t ** 3) * p3


def _side_stats(g: np.ndarray, path, d, t, skip: np.ndarray | None = None):
    """Nilai piksel di KEDUA sisi garis (tegak lurus arah garis), sedikit di luar tebal garisnya."""
    n = np.array([-d[1], d[0]], np.float32)
    H, W = g.shape
    side = ([], [])
    for k, (py, px) in enumerate(path):
        if k < 2:
            continue
        for s in np.arange(t / 2.0 + 2.0, t / 2.0 + 8.0, 1.5):
            for si, sg in enumerate((1.0, -1.0)):
                qx, qy = int(round(px + n[0] * s * sg)), int(round(py + n[1] * s * sg))
                if 0 <= qx < W and 0 <= qy < H and (skip is None or not skip[qy, qx]):
                    side[si].append(float(g[qy, qx]))
    return [np.array(v, np.float32) for v in side]


def is_bubble_edge(g: np.ndarray, path, d, t, contour_dist: np.ndarray | None = None,
                   skip: np.ndarray | None = None) -> bool:
    """Apakah potongan garis ini TEPI BALON (bukan garis objek: tembok, rambut, garis kecepatan)?
    1) berimpit dengan kontur balon yang terdeteksi, atau
    2) satu sisinya bidang terang & rata (isi balon), sisi lainnya jelas berbeda."""
    if contour_dist is not None:
        near = [contour_dist[py, px] <= max(4.0, t + 2) for py, px in path]
        if np.mean(near) >= 0.7:
            return True
    a, b = _side_stats(g, path, d, t, skip)      # area bekas teks tidak ikut dinilai
    if len(a) < 12 or len(b) < 12:
        return False
    for inner, outer in ((a, b), (b, a)):
        bright = float(np.median(inner)) >= 205 and float((inner >= 190).mean()) >= 0.85
        flat = float((inner < 150).mean()) <= 0.03 and \
            float(np.percentile(inner, 75) - np.percentile(inner, 25)) <= 20
        # sisi luar berbeda: lebih gelap, atau bertekstur (raster / gambar: ada titik-titik gelap)
        differs = (abs(float(np.median(outer)) - float(np.median(inner))) >= 35
                   or float((outer < 150).mean()) >= 0.06 or float(outer.std()) >= 30)
        if bright and flat and differs:
            return True
    return False


def repair(original: np.ndarray, cleaned: np.ndarray, rects, lh: float = 16.0, log=None,
           text_mask: np.ndarray | None = None, bubble_polys=None, only_bubbles: bool = True) -> np.ndarray:
    """Sambung garis yang terputus di sekitar kotak-kotak `rects` (area yang dibersihkan)."""
    H, W = cleaned.shape[:2]
    out = cleaned
    drawn = 0
    changed_all = np.abs(cleaned.astype(np.int16) - original.astype(np.int16)).max(axis=2) > 12
    for r in rects:
        x, y, w, h = (int(v) for v in r)
        e = int(max(30, lh * 2.5))
        x0, y0, x1, y1 = max(0, x - e), max(0, y - e), min(W, x + w + e), min(H, y + h + e)
        ch = changed_all[y0:y1, x0:x1]
        if ch.sum() < 20:
            continue
        ch_d = cv2.dilate(ch.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        rmask = np.zeros(ch.shape, bool)                 # kotak teks (area yang dibersihkan)
        rmask[max(0, y - y0 - 3):y + h - y0 + 3, max(0, x - x0 - 3):x + w - x0 + 3] = True
        C = out[y0:y1, x0:x1]
        g = cv2.cvtColor(C, cv2.COLOR_BGR2GRAY)
        # garis di gambar ASLI (sebelum teks dihapus): bukti bahwa garis memang lewat di sana
        go = cv2.cvtColor(original[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        orig_dark = cv2.erode(go, np.ones((3, 3), np.uint8)) < 110
        # huruf teks asli bukan bukti garis
        tmask = (np.zeros_like(go, bool) if text_mask is None else
                 cv2.dilate((text_mask[y0:y1, x0:x1] > 0).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0)
        dark = (g < 110).astype(np.uint8)
        # garis = bagian gelap yang memanjang (bukan butiran raster): opening dengan ruas pendek
        L = 9
        lines = np.zeros_like(dark)
        for ang in range(0, 180, 15):
            k = np.zeros((L, L), np.uint8)
            c = L // 2
            dx, dy = np.cos(np.radians(ang)) * c, np.sin(np.radians(ang)) * c
            cv2.line(k, (int(round(c - dx)), int(round(c - dy))), (int(round(c + dx)), int(round(c + dy))), 1, 1)
            lines |= cv2.morphologyEx(dark, cv2.MORPH_OPEN, k)
        thick_area = cv2.distanceTransform(dark, cv2.DIST_L2, 3) > 4.0      # area hitam pekat bukan garis
        lines = (lines > 0) & ~(cv2.dilate(thick_area.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0)
        if not lines.any():
            continue
        sk = _thin(lines)
        dist = cv2.distanceTransform(lines.astype(np.uint8), cv2.DIST_L2, 3)
        cdist = None
        if bubble_polys:
            cm = np.full(g.shape, 255, np.uint8)
            for poly in bubble_polys:
                pts_ = np.asarray(poly, np.int32).reshape(-1, 2) - np.array([x0, y0], np.int32)
                if len(pts_) >= 3:
                    cv2.polylines(cm, [pts_], True, 0, 1)
            if (cm == 0).any():
                cdist = cv2.distanceTransform(cm, cv2.DIST_L2, 3)
        ends = []
        for (ey, ex) in _endpoints(sk):
            path = _trace(sk, ey, ex, 18)
            if len(path) < 10:
                continue
            P = np.array([[px, py] for py, px in path], np.float32)
            # arah = garis yang paling cocok dengan jejak (2-3 piksel paling ujung sering serpihan)
            Q = P[2:] if len(P) > 8 else P
            vx, vy, _cx, _cy = cv2.fitLine(Q, cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
            d = np.array([vx, vy], np.float32)
            if float(d @ (P[0] - P[-1])) < 0:
                d = -d                                  # menghadap keluar dari ujung garis
            if float(np.hypot(*(P[0] - P[-1]))) < 4:
                continue
            # kelengkungan garis di dekat ujung (radian per piksel): beda arah paruh dekat & paruh jauh
            kappa = 0.0
            if len(P) >= 12:
                h2 = len(P) // 2
                a1 = cv2.fitLine(P[1:h2 + 1], cv2.DIST_L2, 0, 0.01, 0.01).ravel()[:2]
                a2 = cv2.fitLine(P[h2:], cv2.DIST_L2, 0, 0.01, 0.01).ravel()[:2]
                cosang = abs(float(a1 @ a2)) / max(1e-6, float(np.hypot(*a1) * np.hypot(*a2)))
                kappa = float(np.arccos(np.clip(cosang, -1, 1))) / max(1.0, len(P) / 2.0)
            # ujung harus menghadap ke area yang dibersihkan (garis 'kepotong' oleh hapus teks)
            hit = False
            for s in range(2, 9):
                qx, qy = int(round(ex + d[0] * s)), int(round(ey + d[1] * s))
                if 0 <= qy < ch_d.shape[0] and 0 <= qx < ch_d.shape[1] and ch_d[qy, qx]:
                    hit = True
                    break
            if not hit:
                continue
            # jarak ke tepi di tengah garis setebal w kira-kira (w + 1) / 2
            t = float(np.median([dist[py, px] for py, px in path])) * 2.0 - 1.0
            col = np.median(np.array([C[py, px] for py, px in path]), axis=0)
            # hanya tepi balon yang disambung; garis objek (tembok, rambut, garis kecepatan) dibiarkan
            if only_bubbles and not is_bubble_edge(g, path, d, max(1.0, t), cdist, skip=ch_d | tmask | rmask):
                continue
            ends.append({"p": np.array([ex, ey], np.float32), "d": d, "t": max(1.0, t), "col": col,
                         "k": kappa})
        if len(ends) < 2:
            continue
        maxgap = lh * 6.0
        cos_lim = np.cos(np.radians(52))
        pairs = []
        for i in range(len(ends)):
            for j in range(i + 1, len(ends)):
                a, b = ends[i], ends[j]
                v = b["p"] - a["p"]
                dd = float(np.hypot(*v))
                if dd < 4 or dd > maxgap:
                    continue
                u = v / dd
                ci, cj = float(a["d"] @ u), float(b["d"] @ (-u))
                # garis melengkung (balon oval): tali busur boleh menyimpang dari arah ujung,
                # asal kedua ujung tetap saling menghadap
                if ci < cos_lim or cj < cos_lim or ci + cj < 1.55:
                    continue
                if not (0.45 <= a["t"] / b["t"] <= 2.2):
                    continue
                if float(np.abs(a["col"].astype(np.float32) - b["col"].astype(np.float32)).max()) > 60:
                    continue                    # warna garis berbeda: bukan garis yang sama
                # belokan sambungan harus sesuai kelengkungan garis aslinya
                # (garis lurus -> sambungan hampir lurus; oval -> ikut melengkung)
                turn = float(np.arccos(np.clip(float(a["d"] @ (-b["d"])), -1, 1)))
                expect = (a["k"] + b["k"]) / 2.0 * dd
                if turn > expect * 1.6 + 0.26:
                    continue
                # celahnya harus (sebagian besar) di area yang dibersihkan
                hand = dd / 3.0
                pts = _bezier(a["p"], a["p"] + a["d"] * hand, b["p"] + b["d"] * hand, b["p"], 24)
                # kurva berkelok (bentuk S) = pasangan salah
                dv = np.diff(pts, axis=0)
                cr = dv[:-1, 0] * dv[1:, 1] - dv[:-1, 1] * dv[1:, 0]
                big = cr[np.abs(cr) > 1e-3]
                if big.size and (big > 0).any() and (big < 0).any() and \
                        min((big > 0).sum(), (big < 0).sum()) > 2:
                    continue
                # bukti: di gambar asli jalur sambungan ini memang garis gelap (lalu ikut terhapus)
                gap_pts = pts[3:-3] if len(pts) > 8 else pts
                iy = np.clip(np.round(gap_pts[:, 1]).astype(int), 0, orig_dark.shape[0] - 1)
                ix = np.clip(np.round(gap_pts[:, 0]).astype(int), 0, orig_dark.shape[1] - 1)
                free = ~tmask[iy, ix]                   # titik jalur yang bukan huruf
                if free.sum() < max(4, 0.3 * len(gap_pts)):
                    continue
                if float(orig_dark[iy, ix][free].mean()) < 0.75:
                    continue
                inside = np.mean([ch_d[min(ch_d.shape[0] - 1, int(round(py))), min(ch_d.shape[1] - 1, int(round(px)))]
                                  for px, py in pts])
                if inside < 0.5:
                    continue
                cost = dd * (2.2 - ci - cj)
                pairs.append((cost, i, j, pts))
        pairs.sort(key=lambda t: t[0])
        used = set()
        for cost, i, j, pts in pairs:
            if i in used or j in used:
                continue
            used.update((i, j))
            a, b = ends[i], ends[j]
            t = (a["t"] + b["t"]) / 2.0
            col = tuple(int(v) for v in ((a["col"].astype(np.float32) + b["col"].astype(np.float32)) / 2))
            if out is cleaned:
                out = cleaned.copy()
                C = out[y0:y1, x0:x1]
            SH = 4
            ip = np.round((pts + np.array([x0, y0], np.float32)) * (1 << SH)).astype(np.int32)
            cv2.polylines(out, [ip], False, col, max(1, int(round(t))), cv2.LINE_AA, SH)
            drawn += 1
    if log and drawn:
        log(f"Garis balon yang terputus disambung: {drawn}")
    return out
