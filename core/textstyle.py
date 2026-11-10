"""Baca gaya warna teks asli: warna isi huruf, garis tepi (warna + tebal), dan gradasi.

Cara kerja (tanpa model AI tambahan, cepat):
1. Ambil area teks (text_rect) + cincin latar di sekelilingnya.
2. Kelompokkan warna piksel jadi beberapa cluster (k-means di ruang warna Lab).
3. Cluster yang menguasai cincin luar = LATAR.
4. Cluster yang membentuk "inti" goresan (piksel jauh dari tepi cluster) & kontras dengan latar = ISI HURUF.
5. Cluster yang membungkus isi huruf dengan tebal >= 2 px dan BUKAN warna antara isi & latar
   (bukan tepi antialias) = GARIS TEPI.
6. Gradasi: warna isi huruf bagian atas vs bawah blok (atau atas/bawah huruf bila satu baris).
"""
from __future__ import annotations

import cv2
import numpy as np

from .models import TextBlock


def _hex(bgr) -> str:
    b, g, r = (int(round(float(v))) for v in bgr)
    return "#{:02X}{:02X}{:02X}".format(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def _snap(bgr):
    """Hampir hitam -> hitam, hampir putih -> putih (hindari #0B0D0C dari kompresi JPEG)."""
    lab = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2LAB)[0, 0].astype(int)
    chroma = abs(lab[1] - 128) + abs(lab[2] - 128)
    if chroma < 14 and lab[0] < 60:
        return np.array([0, 0, 0])
    if chroma < 14 and lab[0] > 225:
        return np.array([255, 255, 255])
    return np.asarray(bgr, float)


def _enclosed_fill(crop, m, sh):
    """Bila cluster m adalah GARIS TEPI (huruf terang bergaris tepi gelap), kembalikan
    (piksel isi huruf, tebal garis tepi). Ciri: lubang di dalam m luasnya sebanding dengan m dan
    sebagian berbentuk memanjang (bagian dalam huruf H, E, L…), bukan rongga bulat huruf O/A."""
    cnts, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is None:
        return None
    holes = np.zeros_like(m)
    total, elong = 0.0, 0.0
    for i, hcur in enumerate(hier[0]):
        if hcur[3] < 0:
            continue
        a = cv2.contourArea(cnts[i])
        if a < 6:
            continue
        per = cv2.arcLength(cnts[i], True) or 1.0
        cv2.drawContours(holes, cnts, i, 1, -1)
        total += a
        if 4 * np.pi * a / (per * per) < 0.35:
            elong += a
    area = float(m.sum())
    if area <= 0 or total < 0.6 * area or elong < 0.2 * total:
        return None
    holes &= (1 - m)
    px = crop[holes > 0]
    if len(px) < 20:
        return None
    d = cv2.distanceTransform((1 - holes).astype(np.uint8), cv2.DIST_L2, 3)
    width = float(np.percentile(d[m > 0], 70))
    return px, max(2.0, width)


def analyze(img: np.ndarray, b: TextBlock) -> dict | None:
    rect = b.text_rect if b.text_rect and len(b.text_rect) == 4 else [b.x, b.y, b.w, b.h]
    x, y, w, h = (int(v) for v in rect)
    H, W = img.shape[:2]
    sh = float(b.src_h or max(8, min(w, h) * 0.25))
    p = int(max(4, sh * 0.6))
    x0, y0, x1, y1 = max(0, x - p), max(0, y - p), min(W, x + w + p), min(H, y + h + p)
    crop = img[y0:y1, x0:x1]
    if crop.size == 0 or min(crop.shape[:2]) < 6:
        return None
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).astype(np.float32)
    data = lab.reshape(-1, 3)
    K = 5
    if len(data) > 60000:   # cukup sampel untuk cluster; label dihitung ulang untuk semua piksel
        idx = np.random.default_rng(1).choice(len(data), 60000, replace=False)
        sample = data[idx]
    else:
        sample = data
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    try:
        _c, _l, centers = cv2.kmeans(sample, K, None, crit, 2, cv2.KMEANS_PP_CENTERS)
    except cv2.error:
        return None
    d = ((data[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
    lbl = d.argmin(1).reshape(crop.shape[:2])

    inner = np.zeros(lbl.shape, bool)
    inner[y - y0:y - y0 + h, x - x0:x - x0 + w] = True
    ring = ~inner
    ia, ra = max(1, int(inner.sum())), max(1, int(ring.sum()))
    cin = np.bincount(lbl[inner].ravel(), minlength=K).astype(float)
    crg = np.bincount(lbl[ring].ravel(), minlength=K).astype(float) if ring.any() else np.zeros(K)
    # warna TEKS jauh lebih sering muncul di dalam kotak teks daripada di latar sekelilingnya
    ratio = (cin / ia + 1e-6) / (crg / ra + 1e-3)
    k3 = np.ones((3, 3), np.uint8)
    text_ks, info = [], {}
    for k in range(K):
        if cin[k] < max(20, ia * 0.01) or ratio[k] < 2.0:
            continue
        m = ((lbl == k) & inner).astype(np.uint8)
        dist = cv2.distanceTransform(cv2.copyMakeBorder(m, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0),
                                     cv2.DIST_L2, 3)[1:-1, 1:-1]
        if dist.max() < 1.4:          # sangat tipis = tepi antialias, bukan warna huruf
            continue
        # bentuk huruf: komponen setinggi huruf/kata, bukan gumpalan latar
        n, cl, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        lp = 0
        for i in range(1, n):
            _x, _y, cw_, ch_, ca_ = st[i]
            if 0.3 * sh <= ch_ <= 2.2 * sh and 0.06 <= ca_ / float(cw_ * ch_) <= 0.9:
                lp += ca_
        text_ks.append(k)
        info[k] = (m, dist, lp / max(1.0, float(m.sum())))
    if not text_ks:
        return None
    bg_ks = [k for k in range(K) if k not in text_ks]
    bgmask = np.isin(lbl, bg_ks)
    cbg = np.median(lab.reshape(-1, 3)[bgmask.ravel()], axis=0) if bgmask.any() else centers[0]

    def touch_bg(k):
        m = (lbl == k).astype(np.uint8)
        r = (cv2.dilate(m, k3, iterations=2) > 0) & (m == 0) & inner
        return float(bgmask[r].mean()) if r.any() else 0.0

    # isi huruf: warna teks yang dibungkus (paling sedikit menyentuh latar);
    # bila hanya satu warna teks -> itu isinya
    # urutkan: banyak di dalam kotak & kontras dengan latar (bukan sekadar latar yang tidak rata)
    text_ks.sort(key=lambda k: -(np.sqrt(cin[k]) * float(np.linalg.norm(centers[k] - cbg))
                                 * (0.15 + info[k][2]) * np.log1p(min(ratio[k], 50.0))))
    text_ks = [k for k in text_ks if float(np.linalg.norm(centers[k] - cbg)) >= 30] or text_ks[:1]
    if len(text_ks) == 1:
        best, outl = text_ks[0], None
    else:
        a_, b_ = text_ks[0], text_ks[1]
        if cin[b_] < 0.25 * cin[a_]:
            best, outl = a_, None
        else:
            ta, tb = touch_bg(a_), touch_bg(b_)
            if abs(ta - tb) < 0.15:      # keduanya sama-sama di latar -> bukan pasangan isi/tepi
                best, outl = a_, None
            else:
                best, outl = (a_, b_) if ta <= tb else (b_, a_)
    # garis tepi tebal di latar yang warnanya sama dengan isi huruf (huruf putih bergaris hitam di
    # halaman putih): isi hurufnya berupa "lubang" berbentuk huruf di dalam garis tepi
    if outl is None:
        swap = _enclosed_fill(crop, (lbl == best).astype(np.uint8), sh)
        if swap is not None:
            inside_px, width = swap
            li = cv2.cvtColor(np.uint8([[np.median(inside_px, axis=0)]]), cv2.COLOR_BGR2LAB)[0, 0].astype(float)
            lo2 = cv2.cvtColor(np.uint8([[np.median(crop[(lbl == best) & inner], axis=0)]]),
                               cv2.COLOR_BGR2LAB)[0, 0].astype(float)
            if abs(li[0] - lo2[0]) < 90 and np.linalg.norm(li - lo2) < 110:
                swap = None          # bukan garis tepi asli (hanya tepi huruf yang lebih gelap)
        if swap is not None:
            res0 = {"color": _hex(_snap(np.median(inside_px, axis=0))), "color2": "",
                    "stroke_color": _hex(_snap(np.median(crop[(lbl == best) & inner], axis=0))),
                    "stroke_width": int(round(min(width, sh * 0.25)))}
            return res0
    fill_m, fill_d = info[best][:2]
    fill_px = crop[fill_m > 0]
    fill_core = crop[(fill_m > 0) & (fill_d >= max(1.0, sh * 0.04))]
    src_px = fill_core if len(fill_core) > 20 else fill_px
    fill = np.median(src_px, axis=0)
    # huruf gelap/terang yang buram (JPEG, diperbesar): ambil bagian terpekatnya
    lum = src_px.mean(axis=1)
    bg_l = float(cbg[0])
    flab = cv2.cvtColor(np.uint8([[fill]]), cv2.COLOR_BGR2LAB)[0, 0].astype(int)
    grayish = abs(flab[1] - 128) + abs(flab[2] - 128) < 14     # hanya huruf hitam/putih/abu-abu
    if lum.size > 30 and grayish:
        # huruf tipis di gambar buram: kebanyakan pikselnya abu-abu antialias -> ambil yang terpekat
        allpx = crop[((lbl == best) | np.isin(lbl, [k for k in text_ks if k != outl])) & inner]
        al = allpx.mean(axis=1) if len(allpx) else lum
        if np.mean(fill) < bg_l:
            fill = np.median(allpx[al <= np.percentile(al, 12)], axis=0) if len(allpx) > 30 else fill
        else:
            fill = np.median(allpx[al >= np.percentile(al, 88)], axis=0) if len(allpx) > 30 else fill
        # manga: huruf abu-abu tua di latar terang hampir selalu aslinya hitam (buram/JPEG), dan sebaliknya
        fl = float(cv2.cvtColor(np.uint8([[fill]]), cv2.COLOR_BGR2LAB)[0, 0, 0])
        if bg_l > 180 and fl < 125:
            fill = np.array([0, 0, 0])
        elif bg_l < 75 and fl > 150:
            fill = np.array([255, 255, 255])
    res = {"color": _hex(_snap(fill)), "color2": "", "stroke_color": "", "stroke_width": 0}
    if outl is not None:
        om = (lbl == outl) & inner
        fm = (lbl == best).astype(np.uint8)
        df = cv2.distanceTransform((1 - fm).astype(np.uint8), cv2.DIST_L2, 3)
        near = om & (df <= sh * 0.3)
        # warna di antara isi huruf & latar (abu-abu pada huruf hitam di putih) = tepi antialias
        lo_ = lab.reshape(crop.shape[:2] + (3,))
        if near.any():
            cn, cf_ = np.median(lo_[near], axis=0), np.median(lo_[fill_m > 0], axis=0)
            seg = cbg - cf_
            t_ = float(np.dot(cn - cf_, seg) / max(1e-6, np.dot(seg, seg)))
            if 0.1 < t_ < 0.9 and np.linalg.norm(cn - (cf_ + t_ * seg)) < 20:
                near = near & False
        if near.any():
            width = float(np.percentile(df[near], 85))
            # garis tepi asli selalu sangat kontras dengan isi huruf (putih/hitam, kuning/merah tua).
            # Tepi huruf yang sedikit lebih gelap karena JPEG / penajaman bukan garis tepi.
            ln_ = np.median(lo_[near], axis=0)
            lf_ = np.median(lo_[fill_m > 0], axis=0)
            dL = abs(float(ln_[0]) - float(lf_[0]))
            dE = float(np.linalg.norm(ln_ - lf_))
            # tebal garis tepi juga harus nyata dibanding tebal goresan huruf
            stroke_w = 2.0 * float(np.median(fill_d[fill_d > 0])) if (fill_d > 0).any() else 0
            if (dL < 90 and dE < 110) or width < max(1.8, 0.35 * stroke_w):
                width = 0
            if width >= 1.8:
                res["stroke_color"] = _hex(_snap(np.median(crop[near], axis=0)))
                res["stroke_width"] = int(round(min(width, sh * 0.25)))

    # gradasi: bagian atas vs bawah isi huruf. Huruf bergradasi bisa terpecah ke beberapa cluster
    # (atas gelap, bawah merah) -> pakai semua warna teks kecuali garis tepi.
    gm = (np.isin(lbl, [k for k in text_ks if k != outl]) & inner).astype(np.uint8)
    if gm.sum() > fill_m.sum():
        fill_m = gm
    rows = np.nonzero((fill_m > 0).any(axis=1))[0]
    if rows.size > 6:
        runs, start = [], rows[0]
        for a, bnext in zip(rows, rows[1:]):
            if bnext != a + 1:
                runs.append((start, a))
                start = bnext
        runs.append((start, rows[-1]))
        runs = [r for r in runs if r[1] - r[0] >= 4]

        def med(ya, yb):
            px = crop[ya:yb + 1][fill_m[ya:yb + 1] > 0]
            return np.median(px, axis=0) if len(px) > 15 else None
        if len(runs) >= 2:
            ct, cb = med(*runs[0]), med(*runs[-1])
        elif runs:
            a0, a1 = runs[0]
            k3 = max(1, (a1 - a0 + 1) // 3)
            ct, cb = med(a0, a0 + k3), med(a1 - k3 + 1, a1)
        else:
            ct = cb = None
        if ct is not None and cb is not None:
            lt = cv2.cvtColor(np.uint8([[ct]]), cv2.COLOR_BGR2LAB)[0, 0].astype(float)
            lb = cv2.cvtColor(np.uint8([[cb]]), cv2.COLOR_BGR2LAB)[0, 0].astype(float)
            colourful = max(abs(lt[1] - 128) + abs(lt[2] - 128), abs(lb[1] - 128) + abs(lb[2] - 128)) > 20
            if colourful and np.linalg.norm(lt - lb) > 28:
                res["color"], res["color2"] = _hex(ct), _hex(cb)
    return res


_CAND_CACHE: dict = {}


def _page_cands(img):
    """Kandidat huruf gelap & terang untuk seluruh halaman (sekali per gambar)."""
    from .detector import _letter_candidates
    key = (id(img), img.shape, int(img[::97, ::89].sum()))
    if key not in _CAND_CACHE:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _CAND_CACHE.clear()
        _CAND_CACHE[key] = (_letter_candidates(g), _letter_candidates(255 - g))
    return _CAND_CACHE[key]


def _in_rect(cands, rect, ox, oy):
    x, y, w, h = rect
    return [(c[0] - ox, c[1] - oy, c[2], c[3]) for c in cands
            if x - 2 <= c[0] + c[2] / 2 <= x + w + 2 and y - 2 <= c[1] + c[3] / 2 <= y + h + 2]


def analyze_letters(img: np.ndarray, b: TextBlock) -> dict | None:
    """Pakai detektor huruf (dua arah: huruf gelap & huruf terang) untuk menemukan ISI huruf,
    lalu baca warna isi, garis tepi di sekelilingnya, dan gradasi."""
    rect = b.text_rect if b.text_rect and len(b.text_rect) == 4 else [b.x, b.y, b.w, b.h]
    x, y, w, h = (int(v) for v in rect)
    H, W = img.shape[:2]
    sh = float(b.src_h or max(8, min(w, h) * 0.25))
    p = int(max(6, sh * 0.8))
    x0, y0, x1, y1 = max(0, x - p), max(0, y - p), min(W, x + w + p), min(H, y + h + p)
    crop = img[y0:y1, x0:x1]
    if crop.size == 0 or min(crop.shape[:2]) < 8:
        return None
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    pd, pl = _page_cands(img)
    dark = _in_rect(pd, [x, y, w, h], x0, y0)
    light = _in_rect(pl, [x, y, w, h], x0, y0)

    def inside(c, outer):
        return any(o[0] - 1 <= c[0] and o[1] - 1 <= c[1] and c[0] + c[2] <= o[0] + o[2] + 1
                   and c[1] + c[3] <= o[1] + o[3] + 1 for o in outer)
    # huruf terang yang masing-masing berada di dalam "huruf" gelap = huruf terang bergaris tepi gelap
    # (dan sebaliknya). Selain itu pakai arah yang hurufnya lebih banyak.
    l_in = sum(inside(c, dark) for c in light)
    d_in = sum(inside(c, light) for c in dark)
    if light and l_in >= 0.6 * len(light) and len(light) >= 0.5 * len(dark):
        pol, cands = "light", light
    elif dark and d_in >= 0.6 * len(dark) and len(dark) >= 0.5 * len(light):
        pol, cands = "dark", dark
    else:
        pol, cands = ("light", light) if len(light) > len(dark) * 1.3 else ("dark", dark)
    if len(cands) < 2:
        return None
    # mask isi huruf: piksel komponen huruf (ambang lokal relatif terhadap latar sekitar)
    src = (255 - g) if pol == "light" else g
    bgl = cv2.dilate(src, np.ones((9, 9), np.uint8))
    ink = ((src < 170) & (bgl.astype(int) - src > 55)).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    keep = np.zeros(n, bool)
    cset = {(c[0], c[1], c[2], c[3]) for c in cands}
    for i in range(1, n):
        if (int(st[i][0]), int(st[i][1]), int(st[i][2]), int(st[i][3])) in cset:
            keep[i] = True
    fm = keep[lbl].astype(np.uint8)
    if fm.sum() < 20:
        return None
    core = cv2.erode(fm, np.ones((3, 3), np.uint8))
    fill_px = crop[(core if core.sum() > 20 else fm) > 0]
    fill = np.median(fill_px, axis=0)
    res = {"color": _hex(_snap(fill)), "color2": "", "stroke_color": "", "stroke_width": 0}

    # garis tepi: warna di cincin sekitar isi huruf yang berbeda dari isi DAN dari latar jauh
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).astype(np.float32)
    k3 = np.ones((3, 3), np.uint8)
    d_out = cv2.distanceTransform((1 - fm).astype(np.uint8), cv2.DIST_L2, 3)
    near = (d_out > 1.2) & (d_out <= max(2.5, sh * 0.08))
    far = (d_out > sh * 0.35) & (d_out <= sh * 0.7)
    if near.sum() > 20 and far.sum() > 20:
        lf = np.median(lab[fm > 0], axis=0)
        ln = np.median(lab[near], axis=0)
        lfar = np.median(lab[far], axis=0)
        if np.linalg.norm(ln - lf) > 45 and np.linalg.norm(ln - lfar) > 30:
            # tebal: sejauh mana warna tepi masih bertahan dari isi huruf
            close = np.linalg.norm(lab - ln, axis=2) < 30
            width = 0
            for dpx in range(1, int(sh * 0.3) + 1):
                ringd = (d_out > dpx - 1) & (d_out <= dpx)
                if ringd.sum() == 0 or close[ringd].mean() < 0.5:
                    break
                width = dpx
            if width >= 2:
                res["stroke_color"] = _hex(_snap(np.median(crop[near], axis=0)))
                res["stroke_width"] = int(width)

    # gradasi atas -> bawah
    rows = np.nonzero(fm.any(axis=1))[0]
    runs = []
    if rows.size:
        start = rows[0]
        for a_, b_ in zip(rows, rows[1:]):
            if b_ != a_ + 1:
                runs.append((start, a_))
                start = b_
        runs.append((start, rows[-1]))
        runs = [r for r in runs if r[1] - r[0] >= 4]

    def med(ya, yb):
        px = crop[ya:yb + 1][core[ya:yb + 1] > 0]
        return np.median(px, axis=0) if len(px) > 15 else None
    ct = cb = None
    if len(runs) >= 2:
        ct, cb = med(*runs[0]), med(*runs[-1])
    elif runs:
        a0, a1 = runs[0]
        k = max(1, (a1 - a0 + 1) // 3)
        ct, cb = med(a0, a0 + k), med(a1 - k + 1, a1)
    if ct is not None and cb is not None:
        lt = cv2.cvtColor(np.uint8([[ct]]), cv2.COLOR_BGR2LAB)[0, 0].astype(float)
        lb = cv2.cvtColor(np.uint8([[cb]]), cv2.COLOR_BGR2LAB)[0, 0].astype(float)
        colourful = max(abs(lt[1] - 128) + abs(lt[2] - 128), abs(lb[1] - 128) + abs(lb[2] - 128)) > 20
        if colourful and np.linalg.norm(lt - lb) > 28:
            res["color"], res["color2"] = _hex(ct), _hex(cb)
    return res


def apply(img: np.ndarray, b: TextBlock, size_hint: float | None = None) -> bool:
    """Isi warna/garis tepi blok dari gaya teks aslinya. True bila berhasil dibaca."""
    try:
        r = analyze(img, b)
    except Exception:
        r = None
    if not r:
        return False
    b.color = r["color"]
    b.color2 = r["color2"]
    if r["stroke_width"]:
        b.stroke_color = r["stroke_color"]
        b.stroke_width = max(1, int(r["stroke_width"]))
    else:
        b.stroke_width = 0
    return True
