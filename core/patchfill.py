"""Patch Tool otomatis (seperti Patch Tool / Content-Aware Fill di Photoshop).

1. NILAI KEMULUSAN hasil restore: area bekas teks dibandingkan dengan latar di sekelilingnya --
   warna rata-rata, kekasaran tekstur (raster / butiran), noda kabur (hasil AI yang 'meleleh'),
   dan sambungan di tepi area (garis / loncatan warna). Hasil: skor 0..1 (1 = menyatu sempurna).
2. Bila belum mulus: CARI AREA YANG SAMA di halaman -- potongan halaman yang tepinya paling cocok
   dengan tepi area yang ditambal (dicari dengan template matching bertopeng), isinya bersih
   (bukan teks / bagian yang sudah diubah) dan teksturnya mirip latar sekitar.
3. TEMPEL dengan pembauran (Poisson / seamless clone): warna & terang disesuaikan dengan sekitarnya,
   tekstur aslinya tetap. Hasil ditempel hanya bila skornya memang lebih baik.

Dipakai otomatis setelah hapus teks, dan manual lewat alat Patch (tandai area dengan path).
"""
from __future__ import annotations

import cv2
import numpy as np

GOOD = 0.72          # skor minimum yang dianggap sudah rapi
MAX_AUTO = 12        # maksimum area yang ditambal otomatis per halaman (mode hemat: lebih sedikit)


def _gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def _ring(mask: np.ndarray, r: int) -> np.ndarray:
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    return (cv2.dilate(mask, k) > 0) & ~(cv2.dilate(mask, np.ones((3, 3), np.uint8)) > 0)


def _hf(gray: np.ndarray) -> np.ndarray:
    """Energi detail halus (butiran / raster / garis tipis)."""
    g = gray.astype(np.float32)
    return np.abs(g - cv2.GaussianBlur(g, (0, 0), 1.2))


def _edges(gray: np.ndarray) -> np.ndarray:
    """Garis / tepi bentuk (bukan butiran raster): Canny pada gambar yang sedikit diburamkan."""
    g = cv2.GaussianBlur(gray.astype(np.uint8) if gray.dtype != np.uint8 else gray, (0, 0), 2.0)
    return cv2.Canny(g, 40, 100) > 0


def structure(gray: np.ndarray, L: int = 15) -> np.ndarray:
    """Garis gelap (tepi balon, tepi kotak, garis gambar) -- ruas lurus >= L px yang tipis.
    Butiran raster (titik terpisah) dan noda / bercak tebal tidak termasuk."""
    dark = (gray < 110).astype(np.uint8)
    if not dark.any():
        return np.zeros(gray.shape, bool)
    out = np.zeros_like(dark)
    c = L // 2
    for ang in range(0, 180, 15):
        k = np.zeros((L, L), np.uint8)
        dx, dy = np.cos(np.radians(ang)) * c, np.sin(np.radians(ang)) * c
        cv2.line(k, (int(round(c - dx)), int(round(c - dy))), (int(round(c + dx)), int(round(c + dy))), 1, 1)
        out |= cv2.morphologyEx(dark, cv2.MORPH_OPEN, k)
    # bagian tebal (bercak / noda / area hitam) bukan garis
    thick = cv2.distanceTransform(dark, cv2.DIST_L2, 3) > 3.5
    thick = cv2.dilate(thick.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    return (out > 0) & ~thick


def smoothness(img: np.ndarray, mask: np.ndarray, ring_px: int | None = None, detail: dict | None = None) -> float:
    """Skor kemulusan area `mask` di gambar `img` dibanding latar sekitarnya (0..1)."""
    m8 = (mask > 0).astype(np.uint8)
    bx, by, bw, bh = cv2.boundingRect(m8)
    if bw == 0 or bh == 0:
        return 1.0
    size = max(bw, bh)
    r = ring_px or int(np.clip(size * 0.35, 6, 40))
    # hanya potongan di sekitar area (cepat walau halaman besar)
    H, W = m8.shape[:2]
    e = r + 8
    y0, y1 = max(0, by - e), min(H, by + bh + e)
    x0, x1 = max(0, bx - e), min(W, bx + bw + e)
    img, m = img[y0:y1, x0:x1], m8[y0:y1, x0:x1] > 0
    if m.sum() < 12:
        return 1.0
    ring = _ring(m.astype(np.uint8) * 255, r)
    if ring.sum() < 20:
        return 1.0
    g = _gray(img).astype(np.float32)
    hf = _hf(g)
    # garis / bentuk gelap (tepi balon, kotak) tidak dinilai: itu bagian gambar, bukan cacat
    struct = cv2.dilate(structure(g).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    m2, ring2 = m & ~struct, ring & ~struct
    if m2.sum() >= 12 and ring2.sum() >= 20:
        m, ring = m2, ring2
    gi, gr = g[m], g[ring]

    def mad(v):
        return 1.4826 * float(np.median(np.abs(v - np.median(v))))

    # statistik tahan pencilan: garis balon / tepi panel di sekeliling tidak dianggap 'latar'
    mi, mr = float(np.median(gi)), float(np.median(gr))
    d_mean = abs(mi - mr) / 40.0
    hi, hr = float(np.median(hf[m])), float(np.median(hf[ring]))
    d_tex = abs(np.log((hi + 2.0) / (hr + 2.0))) / 0.9
    si, sr = mad(gi), mad(gr)
    d_std = abs(np.log((si + 4.0) / (sr + 4.0))) / 1.0
    # sambungan: loncatan terang tepat di tepi area dibanding variasi biasa di latar
    edge = (_ring(m.astype(np.uint8) * 255, 2) | (m & ~(cv2.erode(m.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0))) & ~struct
    sm = cv2.GaussianBlur(g, (0, 0), 1.5)
    gx, gy = cv2.Sobel(sm, cv2.CV_32F, 1, 0), cv2.Sobel(sm, cv2.CV_32F, 0, 1)
    gm = np.hypot(gx, gy)
    d_seam = (max(0.0, float(np.median(gm[edge])) / (float(np.median(gm[ring])) + 6.0) - 1.15) / 0.8
              if edge.sum() >= 10 else 0.0)
    # noda besar di dalam area (bercak gelap / terang yang tidak ada di latar)
    blob = (np.abs(cv2.GaussianBlur(g, (0, 0), 3.0) - mr) > max(35.0, sr * 1.6 + 10)) & m
    ring_blob = (np.abs(cv2.GaussianBlur(g, (0, 0), 3.0) - mr) > max(35.0, sr * 1.6 + 10)) & ring
    d_blob = max(0.0, float(blob.sum()) / max(1.0, float(m.sum()))
                 - float(ring_blob.sum()) / max(1.0, float(ring.sum()))) / 0.15
    # garis / bentuk di dalam area yang tidak ada di sekelilingnya (mis. garis tersalin, coretan)
    ed = _edges(g.astype(np.uint8))
    ei, er = float(ed[m].mean()), float(ed[ring].mean())
    d_edge = max(0.0, ei - er * 1.3 - 0.01) / 0.03
    parts = {"mean": d_mean, "tex": d_tex, "std": d_std, "seam": d_seam, "blob": d_blob, "edge": d_edge}
    if detail is not None:
        detail.update(parts)
    bad = d_mean ** 2 + d_tex ** 2 + 0.6 * d_std ** 2 + d_seam ** 2 + d_blob ** 2 + d_edge ** 2
    return float(np.exp(-0.5 * bad))


def find_source(img: np.ndarray, mask: np.ndarray, avoid: np.ndarray | None = None,
                search: int | None = None, low_end: bool = False, strict: bool = True):
    """Posisi (dx, dy) potongan halaman yang paling cocok untuk menambal `mask`:
    tepi sekitarnya mirip, isinya bersih dan teksturnya mirip latar. None bila tidak ada."""
    H, W = mask.shape[:2]
    m = (mask > 0).astype(np.uint8)
    ys, xs = np.nonzero(m)
    if ys.size == 0:
        return None
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    bw, bh = x1 - x0, y1 - y0
    b = int(np.clip(max(bw, bh) * 0.25, 5, 24))          # lebar tepi pembanding
    tx0, ty0, tx1, ty1 = max(0, x0 - b), max(0, y0 - b), min(W, x1 + b), min(H, y1 + b)
    tpl = img[ty0:ty1, tx0:tx1]
    tm = m[ty0:ty1, tx0:tx1]
    ring = (cv2.dilate(tm, np.ones((2 * b + 1, 2 * b + 1), np.uint8)) > 0) & (tm == 0)
    if ring.sum() < 20:
        return None
    th, tw = tpl.shape[:2]
    R = search or int(np.clip(max(bw, bh) * 3, 90, 240 if low_end else 380))
    sx0, sy0 = max(0, tx0 - R), max(0, ty0 - R)
    sx1, sy1 = min(W, tx1 + R), min(H, ty1 + R)
    region = img[sy0:sy1, sx0:sx1]
    if region.shape[0] < th + 2 or region.shape[1] < tw + 2:
        return None
    # skala diperkecil untuk area besar (cepat); diperhalus lagi di skala penuh
    s = 1.0
    big = max(th, tw)
    if big > 60:
        s = 60.0 / big
    if low_end:
        s = min(s, 0.6)

    def rs(a, interp=cv2.INTER_AREA):
        return cv2.resize(a, None, fx=s, fy=s, interpolation=interp) if s < 1.0 else a

    reg_s, tpl_s = rs(region), rs(tpl)
    ring_s = rs(ring.astype(np.uint8) * 255, cv2.INTER_NEAREST)
    if tpl_s.shape[0] < 4 or tpl_s.shape[1] < 4 or reg_s.shape[0] <= tpl_s.shape[0] or reg_s.shape[1] <= tpl_s.shape[1]:
        return None
    msk = cv2.merge([ring_s] * 3).astype(np.float32) / 255.0
    try:
        cost = cv2.matchTemplate(reg_s.astype(np.float32), tpl_s.astype(np.float32), cv2.TM_SQDIFF, mask=msk)
    except cv2.error:
        return None
    cost = cost / max(1.0, float(ring_s.sum() / 255.0) * 3)
    # posisi terlarang: menimpa area yang ditambal sendiri / teks / bagian yang sudah diubah
    av = m.copy() if avoid is None else ((avoid > 0) | (m > 0)).astype(np.uint8)
    av_reg = av[sy0:sy1, sx0:sx1].astype(np.float32)
    # sumber harus bersih pada seluruh kotak (isi + tepi)
    integ = cv2.integral(av_reg)
    hh, ww = th, tw
    ny, nx = av_reg.shape[0] - hh + 1, av_reg.shape[1] - ww + 1
    if ny <= 0 or nx <= 0:
        return None
    blocked = (integ[hh:hh + ny, ww:ww + nx] - integ[0:ny, ww:ww + nx]
               - integ[hh:hh + ny, 0:nx] + integ[0:ny, 0:nx]) > 0
    blocked_s = cv2.resize(blocked.astype(np.uint8), (cost.shape[1], cost.shape[0]),
                           interpolation=cv2.INTER_NEAREST) > 0 if s < 1.0 else blocked[:cost.shape[0], :cost.shape[1]]
    cost = cost.copy()
    cost[blocked_s] = np.inf
    if not np.isfinite(cost).any():
        return None
    # beberapa kandidat terbaik -> pilih yang ISInya paling mirip tekstur latar
    # ciri tekstur hanya di area pencarian (bukan seluruh halaman)
    gl = _gray(region).astype(np.float32)
    g = np.zeros((H, W), np.float32)
    hf = np.zeros((H, W), np.float32)
    g[sy0:sy1, sx0:sx1] = gl
    hf[sy0:sy1, sx0:sx1] = _hf(gl)
    ring_full = np.zeros_like(m, bool)
    ring_full[ty0:ty1, tx0:tx1] = ring
    ref_mean, ref_hf = float(np.median(g[ring_full])), float(np.median(hf[ring_full]))
    ref_std = 1.4826 * float(np.median(np.abs(g[ring_full] - np.median(g[ring_full]))))
    ed = np.zeros((H, W), bool)
    ed[sy0:sy1, sx0:sx1] = _edges(gl.astype(np.uint8))
    ref_ed = float(ed[ring_full].mean())
    flat = cost.ravel()
    order = np.argsort(flat)[:40]
    best, best_score = None, np.inf
    taken = []
    for idx in order:
        c = flat[idx]
        if not np.isfinite(c):
            break
        cy, cx = divmod(int(idx), cost.shape[1])
        px, py = int(round(cx / s)) + sx0, int(round(cy / s)) + sy0
        if any(abs(px - qx) < tw * 0.3 and abs(py - qy) < th * 0.3 for qx, qy in taken):
            continue
        taken.append((px, py))
        # perhalus di skala penuh (±2 px)
        bestl = None
        for dy in range(-2, 3) if s < 1.0 else (0,):
            for dx in range(-2, 3) if s < 1.0 else (0,):
                qx, qy = px + dx, py + dy
                if qx < 0 or qy < 0 or qx + tw > W or qy + th > H:
                    continue
                if av[qy:qy + th, qx:qx + tw].any():
                    continue
                cand = img[qy:qy + th, qx:qx + tw].astype(np.float32)
                d = float(((cand - tpl.astype(np.float32)) ** 2)[ring].mean())
                if bestl is None or d < bestl[0]:
                    bestl = (d, qx, qy)
        if bestl is None:
            continue
        d, qx, qy = bestl
        inner = tm > 0
        gi = g[qy:qy + th, qx:qx + tw][inner]
        hi = hf[qy:qy + th, qx:qx + tw][inner]
        gstd = 1.4826 * float(np.median(np.abs(gi - np.median(gi))))
        pen = (abs(float(np.median(gi)) - ref_mean) / 25.0) ** 2 \
            + (np.log((float(np.median(hi)) + 2) / (ref_hf + 2)) / 0.6) ** 2 \
            + (np.log((gstd + 4) / (ref_std + 4)) / 0.7) ** 2
        ce = float(ed[qy:qy + th, qx:qx + tw][inner].mean())
        if ce > (ref_ed * 1.25 + 0.01 if strict else ref_ed * 1.6 + 0.03):
            continue                     # sumber berisi garis / bentuk yang tidak ada di sekitar area
        pen += (max(0.0, ce - ref_ed) / 0.02) ** 2
        score = d / (ref_std ** 2 + 60.0) + pen
        if score < best_score:
            best_score, best = score, (qx - tx0, qy - ty0)
        if len(taken) >= 12:
            break
    return best


def apply_patch(img: np.ndarray, mask: np.ndarray, offset) -> np.ndarray:
    """Tempel potongan dari posisi (mask digeser `offset`) ke area mask, dengan pembauran."""
    dx, dy = offset
    H, W = mask.shape[:2]
    m = (mask > 0).astype(np.uint8)
    ys, xs = np.nonzero(m)
    pad = 6
    x0, y0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
    x1, y1 = min(W, xs.max() + 1 + pad), min(H, ys.max() + 1 + pad)
    sx0, sy0, sx1, sy1 = x0 + dx, y0 + dy, x1 + dx, y1 + dy
    if sx0 < 0 or sy0 < 0 or sx1 > W or sy1 > H:
        return img
    src = img[sy0:sy1, sx0:sx1].copy()
    dst = img[y0:y1, x0:x1]
    mm = cv2.dilate(m[y0:y1, x0:x1], np.ones((5, 5), np.uint8))
    out = img.copy()
    # pembauran Poisson (warna menyesuaikan sekitar, tekstur dari sumber)
    blended = None
    # Poisson hanya bila tepi area tidak menyentuh garis / bentuk gelap (kalau menyentuh, warnanya
    # 'luber' ke dalam area) -- selain itu: samakan terang lalu baurkan tepi
    edge_ring = _ring(mm * 255, 3)
    gd = _gray(dst)
    poisson_ok = edge_ring.any() and float((gd[edge_ring] < 90).mean()) < 0.02
    try:
        if not poisson_ok:
            raise cv2.error("lewati Poisson")
        mm2 = mm.copy() * 255
        mm2[0, :] = mm2[-1, :] = 0
        mm2[:, 0] = mm2[:, -1] = 0
        if mm2.any():
            canvas = dst.copy()
            ys2, xs2 = np.nonzero(mm2)
            cx, cy = (xs2.min() + xs2.max() + 1) // 2, (ys2.min() + ys2.max() + 1) // 2
            bx0, by0 = xs2.min(), ys2.min()
            bx1, by1 = xs2.max() + 1, ys2.max() + 1
            res = cv2.seamlessClone(src[by0:by1, bx0:bx1], canvas, mm2[by0:by1, bx0:bx1], (int(cx), int(cy)),
                                    cv2.NORMAL_CLONE)
            blended = res
    except cv2.error:
        blended = None
    if blended is None:
        # cadangan: samakan terang rata-rata lalu baurkan tepi
        ring = _ring(mm * 255, 4)
        if ring.any():
            shift = np.median(dst[ring].astype(np.float32), axis=0) - np.median(src[ring].astype(np.float32), axis=0)
            src = np.clip(src.astype(np.float32) + shift, 0, 255).astype(np.uint8)
        a = cv2.GaussianBlur(mm.astype(np.float32), (0, 0), 1.5)[..., None]
        blended = (src * a + dst * (1 - a)).astype(np.uint8)
    region = out[y0:y1, x0:x1]
    sel = mm > 0
    region[sel] = blended[sel]
    return out


TILE = 56          # area lebih besar dari ini ditambal per ubin (seperti menambal sedikit demi sedikit)


def _patch_tiles(img, mask, avoid, low_end, strict=True):
    """Tambal area besar per ubin, dari tepi ke tengah: setiap ubin dicocokkan dengan tepi yang sudah
    benar (latar asli atau ubin yang baru ditambal)."""
    out = img.copy()
    m = (mask > 0).astype(np.uint8)
    ys, xs = np.nonzero(m)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    T = TILE
    left = m.copy()
    av = None if avoid is None else (avoid > 0).astype(np.uint8)
    ok_any = False
    # urutan: ubin yang paling banyak bersinggungan dengan bagian yang sudah benar dulu
    tiles = [(ty, tx) for ty in range(y0, y1, T) for tx in range(x0, x1, T)]
    for _ in range(len(tiles)):
        best, bt = -1.0, None
        for ty, tx in tiles:
            sub = left[ty:ty + T, tx:tx + T]
            if not sub.any():
                continue
            ring = left[max(0, ty - 4):ty + T + 4, max(0, tx - 4):tx + T + 4]
            known = 1.0 - ring.mean()
            if known > best:
                best, bt = known, (ty, tx)
        if bt is None:
            break
        ty, tx = bt
        tmask = np.zeros_like(m)
        tmask[ty:ty + T, tx:tx + T] = left[ty:ty + T, tx:tx + T]
        # bagian yang belum ditambal jangan dipakai sebagai pembanding / sumber
        av2 = left.copy() if av is None else (av | left)
        av2[tmask > 0] = 0
        off = find_source(out, tmask, av2, low_end=low_end, strict=strict)
        if off is not None:
            cand = apply_patch(out, tmask, off)
            if smoothness(cand, tmask) >= smoothness(out, tmask) - 0.02:
                out = cand
                ok_any = True
        left[tmask > 0] = 0
    return out, ok_any


def patch_region(img: np.ndarray, mask: np.ndarray, avoid: np.ndarray | None = None,
                 force: bool = False, low_end: bool = False):
    """Tambal satu area. force=True (alat manual): selalu ditambal bila ada sumber yang cocok.
    Mengembalikan (gambar, skor_sebelum, skor_sesudah, ditambal?).
    Dikerjakan di potongan sekitar area saja (cepat & hemat memori di halaman besar)."""
    m8 = (mask > 0).astype(np.uint8)
    bx, by, bw, bh = cv2.boundingRect(m8)
    if bw == 0:
        b = smoothness(img, mask)
        return img, b, b, False
    H, W = m8.shape
    e = int(np.clip(max(bw, bh) * 3, 90, 240 if low_end else 380)) + 40
    x0, y0, x1, y1 = max(0, bx - e), max(0, by - e), min(W, bx + bw + e), min(H, by + bh + e)
    sub = img[y0:y1, x0:x1]
    av = None if avoid is None else avoid[y0:y1, x0:x1]
    res, b, a, ok = _patch_region_local(sub, m8[y0:y1, x0:x1], av, force, low_end)
    if not ok:
        return img, b, a, False
    out = img.copy()
    out[y0:y1, x0:x1] = res
    return out, b, a, True


def _patch_region_local(img, mask, avoid, force, low_end):
    before = smoothness(img, mask)
    ys, xs = np.nonzero(mask > 0)
    if ys.size == 0:
        return img, before, before, False
    if max(ys.max() - ys.min(), xs.max() - xs.min()) + 1 > TILE * 1.4:
        out, ok = _patch_tiles(img, mask, avoid, low_end, strict=not force)
        if not ok:
            return img, before, before, False
    else:
        off = find_source(img, mask, avoid, low_end=low_end, strict=not force)
        if off is None:
            return img, before, before, False
        out = apply_patch(img, mask, off)
    after = smoothness(out, mask)
    # otomatis: hanya dipakai bila jelas lebih mulus (manual: selalu, pengguna yang menilai)
    if force or (after > before + 0.12 and after >= 0.4):
        return out, before, after, True
    return img, before, before, False


def auto_patch(original: np.ndarray, cleaned: np.ndarray, avoid_rects=(), low_end: bool = False,
               log=None, limit: int | None = None, regions=None) -> np.ndarray:
    """Periksa area yang diubah oleh hapus teks; yang belum mulus ditambal otomatis.
    regions: hanya di sekitar kotak-kotak ini (mis. balon yang baru dibersihkan)."""
    diff = np.abs(cleaned.astype(np.int16) - original.astype(np.int16)).max(axis=2) > 12
    H, W = diff.shape
    if regions is not None:
        keep = np.zeros_like(diff)
        for r in regions:
            x, y, w, h = (int(v) for v in r)
            e = int(max(w, h) * 0.6) + 16
            keep[max(0, y - e):min(H, y + h + e), max(0, x - e):min(W, x + w + e)] = True
        diff &= keep
    if not diff.any():
        return cleaned
    grp = cv2.dilate(diff.astype(np.uint8), np.ones((9, 9), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(grp, connectivity=8)
    avoid = cv2.dilate(diff.astype(np.uint8), np.ones((7, 7), np.uint8))
    for r in avoid_rects:          # teks yang belum dihapus jangan dijadikan sumber
        x, y, w, h = (int(v) for v in r)
        avoid[max(0, y):max(0, y + h), max(0, x):max(0, x + w)] = 1
    out = cleaned
    cands = []
    # garis yang memang ada di gambar asli dan masih ada di hasil: dilindungi
    protect = structure(_gray(original)) & structure(_gray(cleaned))
    protect = cv2.dilate(protect.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a < 40 or w * h > 0.25 * H * W or max(w, h) > 320:
            continue
        m = np.zeros((H, W), np.uint8)
        m[y:y + h, x:x + w] = (lbl[y:y + h, x:x + w] == i) & diff[y:y + h, x:x + w]
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        m = cv2.dilate(m, np.ones((3, 3), np.uint8))
        m[protect] = 0                       # garis asli (tepi balon / kotak) tidak pernah ditimpa
        if m.sum() < 30:
            continue
        sc = smoothness(out, m)
        if sc < GOOD:
            cands.append((sc, m))
    cands.sort(key=lambda t: t[0])
    lim = limit if limit is not None else (MAX_AUTO // 2 if low_end else MAX_AUTO)
    done = 0
    import time
    t_end = time.time() + (0.4 if low_end else 0.8)       # batas waktu per halaman (tetap cepat)
    for sc, m in cands[:lim]:
        if time.time() > t_end:
            break
        out2, b, a, ok = patch_region(out, m, avoid, low_end=low_end)
        if ok:
            out = out2
            done += 1
    if log and cands:
        log(f"Perapian otomatis (patch): {len(cands)} area kurang mulus, {done} ditambal")
    return out
