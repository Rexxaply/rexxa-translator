"""Hapus teks asli (cleaning).

- "fill"   : isi bagian dalam balon dengan warna balon. Cepat & sangat rapi
             untuk balon putih/polos.
- "opencv" : cv2.inpaint (Telea) hanya pada piksel huruf. Cocok untuk teks
             di atas latar sederhana.
- "lama"   : LaMa (AI inpainting) jika paket simple-lama-inpainting terpasang.
             Terbaik untuk teks di atas gambar/arsiran.
- "auto"   : hanya HURUF yang dihapus. Latar rata (putih balon) -> isi warnanya;
             latar bergambar / balon transparan -> generate ulang dengan LaMa (atau opencv).
"""
from __future__ import annotations

import cv2
import numpy as np

from .models import TextBlock

_lama = None
import threading as _threading
_lama_lock = _threading.Lock()


LAMA_MAX_SIDE = 1024        # diperkecil oleh core.perf di mode hemat (PC spesifikasi rendah)


def _get_lama():
    global _lama
    with _lama_lock:          # boleh dipanggil dari thread pemanasan & thread proses bersamaan
        if _lama is None:
            from simple_lama_inpainting import SimpleLama
            _lama = SimpleLama()
    return _lama


def warm_up():
    """Muat model LaMa di latar belakang (beberapa detik di CPU) supaya proses pertama tidak lambat."""
    if _lama is None and lama_available():
        try:
            _get_lama()
        except Exception:
            pass


def lama_available() -> bool:
    try:
        import simple_lama_inpainting  # noqa: F401
        return True
    except ImportError:
        return False


def block_region_mask(shape, b: TextBlock, shrink: int = 0) -> np.ndarray:
    h, w = shape[:2]
    m = np.zeros((h, w), np.uint8)
    if b.mask_poly:
        cv2.fillPoly(m, [np.array(b.mask_poly, np.int32)], 255)
    else:
        cv2.rectangle(m, (b.x, b.y), (b.x + b.w, b.y + b.h), 255, -1)
    if shrink > 0:
        m = cv2.erode(m, np.ones((3, 3), np.uint8), iterations=shrink)
    return m


def contrast_mask(img: np.ndarray, region: np.ndarray, dilate: int = 3) -> np.ndarray:
    """Piksel yang kontras dengan latar (median) di region. Dipakai untuk balon kata:
    sederhana dan bersih untuk huruf gelap di balon terang."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    vals = gray[region > 0]
    if vals.size == 0:
        return np.zeros_like(region)
    bg = np.median(vals)
    txt = ((gray < bg - 60) if bg > 127 else (gray > bg + 60)).astype(np.uint8) * 255
    txt = cv2.bitwise_and(txt, region)
    if dilate:
        txt = cv2.dilate(txt, np.ones((3, 3), np.uint8), iterations=dilate)
        txt = cv2.bitwise_and(txt, cv2.dilate(region, np.ones((3, 3), np.uint8)))
    return txt


def _letter_components(mask: np.ndarray, region: np.ndarray):
    """Komponen berbentuk huruf di dalam region: tidak menyentuh tepi region, tidak terlalu
    besar/kecil. Mengembalikan (mask_huruf, [tinggi huruf])."""
    ys, xs = np.nonzero(region)
    if xs.size == 0:
        return np.zeros_like(mask), []
    rx0, ry0, rx1, ry1 = xs.min(), ys.min(), xs.max(), ys.max()
    rh = max(1, ry1 - ry0)
    m = cv2.bitwise_and(mask, region)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    keep = np.zeros_like(mask)
    heights = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if x <= rx0 or y <= ry0 or x + w >= rx1 or y + h >= ry1:      # menyentuh tepi = latar
            continue
        # satu baris huruf yang saling menempel boleh hampir selebar kotak
        if h < max(4, rh * 0.03) or h > rh * 0.6 or a < 10:
            continue
        fill = a / float(w * h)
        if fill < 0.12 or fill > 0.95:
            continue
        keep[lbl == i] = 255
        heights.append(h)
    return keep, heights


def text_polarity(img: np.ndarray, region: np.ndarray):
    """Tentukan jenis teks di region: 'dark' (huruf gelap, mis. di balon putih) atau
    'light' (huruf putih, sering bergaris tepi hitam, di atas gambar/latar gelap).
    Mengembalikan (polaritas, mask_huruf, median_tinggi_huruf)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    vals = gray[region > 0]
    if vals.size == 0 or np.median(vals) >= 200:
        return "dark", np.zeros_like(region), 0.0
    light, lh = _letter_components((gray >= 215).astype(np.uint8) * 255, region)
    dark, dh = _letter_components((gray <= 80).astype(np.uint8) * 255, region)
    # huruf terang yang dibingkai garis gelap = ciri kuat teks putih bergaris tepi
    if lh:
        ring = cv2.dilate(light, np.ones((3, 3), np.uint8), iterations=3) & ~light
        dark_ring = ((gray <= 110) & (ring > 0)).sum() / max(1, (ring > 0).sum())
    else:
        dark_ring = 0
    if len(lh) >= 2 and (len(lh) >= len(dh) * 0.6 or dark_ring > 0.35):
        return "light", light, float(np.median(lh))
    if dh:
        return "dark", dark, float(np.median(dh))
    return "dark", np.zeros_like(region), 0.0


def text_pixel_mask(img: np.ndarray, region: np.ndarray, dilate: int = 3) -> np.ndarray:
    """Piksel huruf yang harus dihapus di region (huruf + garis tepinya)."""
    pol, letters, h = text_polarity(img, region)
    if letters.any() and pol == "light":
        # huruf putih + SELURUH garis tepi hitamnya: lebarkan sedikit, lalu ikutkan piksel gelap
        # yang menempel (garis tepi tebal), supaya tidak tersisa bercak hitam setelah inpaint
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        r = max(2, int(round(h * 0.18)))
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        txt = cv2.dilate(letters, k)
        darkpx = ((gray <= 115).astype(np.uint8) * 255) & region
        for _ in range(3):
            grow = cv2.dilate(txt, np.ones((3, 3), np.uint8), iterations=2)
            txt = txt | (darkpx & grow)
        # tutup celah antar-huruf supaya tidak tersisa pulau putih/gelap di tengah teks
        kc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(h * 0.7) | 1, int(h * 0.7) | 1))
        txt = cv2.morphologyEx(txt, cv2.MORPH_CLOSE, kc)
        txt = cv2.dilate(txt, np.ones((3, 3), np.uint8), iterations=2)
        return cv2.bitwise_and(txt, cv2.dilate(region, np.ones((3, 3), np.uint8)))
    return contrast_mask(img, region, dilate)


def _text_color(img: np.ndarray, b: TextBlock):
    """Huruf berwarna (mis. emas / merah di manhwa) -> terjemahan memakai warna yang sama."""
    if not (b.text_rect and len(b.text_rect) == 4) or (b.color or "#000000").upper() != "#000000":
        return
    x, y, w, h = (int(v) for v in b.text_rect)
    crop = img[max(0, y):y + h, max(0, x):x + w]
    if crop.size == 0:
        return
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.int16)
    bg = float(np.percentile(gray, 90))
    ink = crop[gray < bg - 70]
    if len(ink) < 30:
        return
    g = ink.mean(axis=1)
    core = ink[g <= np.percentile(g, 50)]               # bagian tengah huruf, bukan tepi antialias
    c = np.median(core, axis=0)
    hexc = lambda v: "#{:02X}{:02X}{:02X}".format(int(v[2]), int(v[1]), int(v[0]))  # noqa: E731
    # gradasi atas -> bawah (seluruh blok teks, khas manhwa): bandingkan baris pertama & terakhir;
    # bila hanya satu baris, bagian atas & bawah hurufnya
    inkm = gray < bg - 70
    rows = inkm.mean(axis=1) > 0.02
    runs, yy = [], 0
    while yy < len(rows):
        if rows[yy]:
            y2 = yy
            while y2 + 1 < len(rows) and rows[y2 + 1]:
                y2 += 1
            if y2 - yy >= 5:
                runs.append((yy, y2))
            yy = y2 + 1
        else:
            yy += 1

    def core_color(y0, y1):
        px = crop[y0:y1][inkm[y0:y1]]
        if len(px) < 15:
            return None
        return np.median(px, axis=0)

    ct = cb = None
    if len(runs) >= 2:
        ct, cb = core_color(*runs[0]), core_color(*runs[-1])
    elif len(runs) == 1:
        y0, y1 = runs[0]
        k = max(1, (y1 - y0 + 1) // 3)
        ct, cb = core_color(y0, y0 + k), core_color(y1 - k + 1, y1 + 1)
    if ct is not None and cb is not None:
        colorful = max(ct.max() - ct.min(), cb.max() - cb.min()) >= 30
        if colorful and np.abs(ct.astype(int) - cb.astype(int)).max() >= 35:
            b.color, b.color2 = hexc(ct), hexc(cb)
            return
    if c.max() - c.min() >= 45:                         # cukup berwarna (bukan hitam/abu-abu)
        b.color = hexc(c)


def auto_style(img: np.ndarray, b: TextBlock):
    """Warna terjemahan mengikuti teks asli: isi huruf, garis tepi, gradasi (core.textstyle).
    Bila gaya tidak terbaca, pakai aturan lama (teks putih di gambar -> putih bergaris hitam)."""
    from . import textstyle
    default_sw = b.stroke_width
    if b.kind != "title" and textstyle.apply(img, b):
        if not b.stroke_width:
            b.stroke_width = default_sw if b.color.upper() in ("#000000",) else 0
        if not getattr(b, "sfx", False):
            _white_outline_text(img, b)
            return
    else:
        _text_color(img, b)
    if getattr(b, "sfx", False):
        try:   # SFX bergaris tepi putih di atas gambar -> terjemahan juga diberi garis tepi putih
            from .sfx import sfx_mask
            m = sfx_mask(img, b)
            if m is not None:
                halo = _halo(img, m, float(b.src_h or 20) * 0.25)
                if (halo > 0).sum() > 0.15 * (m > 0).sum():
                    b.stroke_color = "#FFFFFF"
                    b.stroke_width = max(b.stroke_width, max(2, int(round((b.src_h or 20) * 0.07))))
        except Exception:
            pass
        return
    _dark_bg_outline(img, b)
    _white_outline_text(img, b)
    if b.kind == "bubble":
        return
    region = block_region_mask(img.shape, b)
    pol, _, h = text_polarity(img, region)
    if pol == "light":
        b.color, b.stroke_color = "#FFFFFF", "#000000"
        b.stroke_width = max(b.stroke_width, max(2, int(round(h * 0.12))) if h else 3)


def _dark_bg_outline(img: np.ndarray, b: TextBlock):
    """Teks gelap di atas latar gelap / ramai (biasanya diberi garis tepi putih tebal, mis. narasi
    "I feel chilly..." di panel arsir) -> terjemahan juga diberi garis tepi putih supaya terbaca."""
    if b.stroke_width or not (b.text_rect and len(b.text_rect) == 4) or not _is_darkish(b.color):
        return
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    x, y, w, h = (int(v) for v in b.text_rect)
    sh = float(b.src_h or 16)

    def band(p_in, p_out):
        a0, b0 = max(0, x - p_out), max(0, y - p_out)
        a1, b1 = min(W, x + w + p_out), min(H, y + h + p_out)
        m = np.ones((b1 - b0, a1 - a0), bool)
        i0, j0 = max(0, x - p_in) - a0, max(0, y - p_in) - b0
        i1, j1 = min(W, x + w + p_in) - a0, min(H, y + h + p_in) - b0
        m[max(0, j0):max(0, j1), max(0, i0):max(0, i1)] = False
        v = gray[b0:b1, a0:a1][m]
        return float(np.median(v)) if v.size else 255.0

    outer = band(int(sh * 1.4), int(sh * 3.0))     # latar di luar teks (+ cahaya putihnya)
    if outer < 140:
        b.stroke_color = "#FFFFFF"
        b.stroke_width = max(3, int(round(sh * 0.2)))


def _white_outline_text(img: np.ndarray, b: TextBlock):
    """Huruf asli bergaris tepi putih di atas raster / latar berbintik (mis. "Just between us..." di
    dinding bata): terjemahan juga diberi garis tepi putih supaya gaya & keterbacaannya sama."""
    if b.stroke_width or not (b.text_rect and len(b.text_rect) == 4) or not _is_darkish(b.color):
        return
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    x, y, w, h = (int(v) for v in b.text_rect)
    sh = int(b.src_h or 16)
    crop = gray[max(0, y - sh):y + h + sh, max(0, x - sh):x + w + sh]
    L = (crop < 140).astype(np.uint8)
    if L.sum() < 30:
        return

    def e(r):
        return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2)

    r1 = max(2, int(round(sh * 0.25)))
    near = cv2.dilate(L, e(r1)) & ~cv2.dilate(L, e(1))
    far = cv2.dilate(L, e(r1 + max(3, int(round(sh * 0.6))))) & ~cv2.dilate(L, e(r1 + 2))
    if near.sum() < 30 or far.sum() < 30:
        return
    nw, fw = float((crop[near > 0] >= 215).mean()), float((crop[far > 0] >= 215).mean())
    if nw >= 0.8 and fw <= 0.76 and nw - fw >= 0.1:
        b.stroke_color = "#FFFFFF"
        b.stroke_width = max(2, int(round(sh * 0.16)))


def _is_darkish(c: str) -> bool:
    c = (c or "#000000").lstrip("#")
    try:
        r, g, bb = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except ValueError:
        return True
    return 0.299 * r + 0.587 * g + 0.114 * bb < 90


def page_letters(img: np.ndarray):
    """Kandidat huruf untuk SELURUH halaman (ukuran huruf dinilai relatif ke halaman, bukan kotak)."""
    from .detector import _letter_candidates
    sig = (img.shape, int(img[::97, ::89].sum()))
    if _PL[0] is not img or _PL[1] != sig:          # sekali per gambar (dipanggil berkali-kali)
        _PL[:] = [img, sig, _letter_candidates(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))]
    return _PL[2]


_PL = [None, None, None]


def gap_ok(U, r, lh):
    """Kotak r bersinggungan / dekat dengan kotak gabungan U."""
    gx = max(0, max(U[0], r[0]) - min(U[2], r[0] + r[2]))
    gy = max(0, max(U[1], r[1]) - min(U[3], r[1] + r[3]))
    return gx <= lh * 1.6 and gy <= lh * 1.2


def text_only_mask(img: np.ndarray, b: TextBlock, cands=None):
    """Mask HANYA huruf di area blok (huruf + tanda baca di dekatnya), BUKAN garis balon, rambut,
    atau gambar. Dipakai supaya yang dihapus/di-generate ulang hanya bekas teks.
    Mengembalikan (mask_seukuran_gambar, tinggi_huruf) atau (None, 0) bila tidak ada teks."""
    from .detector import _group_letters
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    x0, y0 = max(0, int(b.x)), max(0, int(b.y))
    x1, y1 = min(W, int(b.x + b.w)), min(H, int(b.y + b.h))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None, 0
    crop = gray[y0:y1, x0:x1]
    if cands is None:
        cands = page_letters(img)
    # huruf yang titik tengahnya di dalam kotak, dalam koordinat kotak
    inside = [(cx - x0, cy - y0, cw, ch) for cx, cy, cw, ch in cands
              if x0 <= cx + cw / 2 < x1 and y0 <= cy + ch / 2 < y1]
    groups = [g for g in _group_letters(inside, crop.shape) if g["n"] >= 2]
    if not groups:
        return None, 0
    # gabungkan baris-baris yang berdekatan jadi satu blok teks, mulai dari kelompok terbesar;
    # kelompok jauh / beda ukuran (mis. pola gambar yang mirip huruf) tidak ikut
    groups.sort(key=lambda g: -g["n"])
    main = groups[0]
    lh = max(4.0, main["med_h"])
    ux, uy, uw, uh = main["rect"]
    U = [ux, uy, ux + uw, uy + uh]
    changed = True
    used = {id(main)}
    while changed:
        changed = False
        for g in groups:
            if id(g) in used or not (0.55 <= g["med_h"] / lh <= 1.8):
                continue
            gx, gy, gw, gh = g["rect"]
            gap_x = max(0, max(U[0], gx) - min(U[2], gx + gw))
            gap_y = max(0, max(U[1], gy) - min(U[3], gy + gh))
            if gap_x <= lh * 1.6 and gap_y <= lh * 1.2:
                U = [min(U[0], gx), min(U[1], gy), max(U[2], gx + gw), max(U[3], gy + gh)]
                used.add(id(g))
                changed = True
    if b.text_rect and len(b.text_rect) == 4:     # area teks hasil deteksi (sudah termasuk ujung baris)
        tx, ty, tw, th = b.text_rect
        tx, ty = tx - x0, ty - y0
        if gap_ok(U, (tx, ty, tw, th), lh):
            U = [min(U[0], tx), min(U[1], ty), max(U[2], tx + tw), max(U[3], ty + th)]
    # bekerja di potongan yang sedikit lebih besar dari kotak: coretan yang terpotong tepi kotak
    # (garis balon, rambut) terlihat utuh, jadi tidak dikira huruf
    P = int(lh * 1.5) + 12
    px0, py0, px1, py1 = max(0, x0 - P), max(0, y0 - P), min(W, x1 + P), min(H, y1 + P)
    ox, oy = x0 - px0, y0 - py0
    pc = gray[py0:py1, px0:px1]
    X0, Y0 = U[0] - lh * 1.2 + ox, U[1] - lh * 0.7 + oy
    X1, Y1 = U[2] + lh * 1.2 + ox, U[3] + lh * 0.7 + oy
    # huruf = jauh lebih gelap dari latar di dekatnya (juga huruf berwarna, mis. emas di balon krem)
    kb = max(3, int(lh * 0.9)) | 1
    near_bg = cv2.dilate(pc, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kb, kb)))
    dark = ((pc < 150) | ((near_bg.astype(np.int16) - pc) > 70)).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    keep = np.zeros(n, bool)
    hs = [lh]
    ix0, iy0, ix1, iy1 = int(max(0, U[0])), int(max(0, U[1])), int(U[2]), int(U[3])
    bg_med = float(np.median(crop[iy0:iy1, ix0:ix1]))
    bg_light = bg_med >= 160                    # teks gelap di latar terang (balon, termasuk balon transparan)
    ring_min = min(185.0, bg_med - 35)          # balon abu-abu / gradasi: bandingkan dengan latarnya sendiri
    bw_, bh_ = x1 - x0, y1 - y0
    # teks bebas: kotaknya hanya perkiraan -> tanda baca di ujung ("...?") boleh sedikit di luar kotak
    slack = lh * 1.5 if b.kind == "free" else 0.0
    for i in range(1, n):
        x, y, w, h, a = st[i]
        # coretan gelap yang SELURUHNYA di dalam blok teks = huruf / tanda baca
        # (boleh setinggi ±2,8 baris: huruf yang tersambung antar baris, mis. "g" dengan "k";
        #  lengkungan garis balon yang masuk ke dalam biasanya lebih tinggi lagi)
        cx, cy = x + w / 2 - ox, y + h / 2 - oy
        if (x >= X0 and y >= Y0 and x + w <= X1 and y + h <= Y1 and h <= lh * 3.2
                and -slack <= cx < bw_ + slack and -slack <= cy < bh_ + slack):
            keep[i] = True
    # bintik raster / butiran kecil di sekitar huruf BUKAN huruf. Coretan kecil (titik "...", titik
    # huruf i, tanda seru) ikut hanya bila menempel ke huruf besar ATAU dikelilingi putih bersih.
    big_ids = [i for i in np.nonzero(keep)[0] if max(st[i][2], st[i][3]) >= lh * 0.45]
    if big_ids:
        bigm = np.isin(lbl, big_ids).astype(np.uint8)
        dist = cv2.distanceTransform(1 - bigm, cv2.DIST_L2, 3)
        for i in np.nonzero(keep)[0]:
            x, y, w, h, a = st[i]
            if max(w, h) >= lh * 0.45:
                continue
            if float(dist[y:y + h, x:x + w][lbl[y:y + h, x:x + w] == i].min()) <= lh * 0.35:
                continue
            p = 3
            sx0, sy0 = max(0, x - p), max(0, y - p)
            sx1, sy1 = min(pc.shape[1], x + w + p), min(pc.shape[0], y + h + p)
            win = pc[sy0:sy1, sx0:sx1]
            ring = lbl[sy0:sy1, sx0:sx1] != i
            if not ring.any() or float(np.median(win[ring])) < 232:
                keep[i] = False
    # huruf dikelilingi latar terang di semua sisi; garis balon / gambar punya sisi luar yang gelap
    if bg_light:
        k3 = np.ones((3, 3), np.uint8)
        for i in np.nonzero(keep)[0]:
            x, y, w, h, a = st[i]
            p = 10
            sx0, sy0, sx1, sy1 = max(0, x - p), max(0, y - p), min(pc.shape[1], x + w + p), min(pc.shape[0], y + h + p)
            comp = (lbl[sy0:sy1, sx0:sx1] == i).astype(np.uint8)
            # cincin 2–6 px dari coretan (lewati tepi abu-abu antialias), tanpa coretan lain
            ring = (cv2.dilate(comp, k3, iterations=6) > 0) & (cv2.dilate(comp, k3, iterations=2) == 0) \
                & (dark[sy0:sy1, sx0:sx1] == 0)
            # balon transparan: latar di sekitar huruf boleh abu-abu asal rata (pita abu-abu)
            rv = pc[sy0:sy1, sx0:sx1][ring].astype(np.float32)
            if rv.size and (rv >= ring_min).mean() < 0.85 and not (rv.std() < 18 and rv.mean() >= 120):
                keep[i] = False
    keep[0] = False
    m = keep[lbl].astype(np.uint8) * 255
    if not m.any():
        return None, 0
    lh = float(np.median(hs))
    r = max(2, int(round(lh * 0.14)))           # tutup juga tepi huruf yang samar (antialias)
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    full = np.zeros((H, W), np.uint8)
    full[py0:py1, px0:px1] = m
    return full, lh


def _halo(img: np.ndarray, tm: np.ndarray, lh: float) -> np.ndarray:
    """Garis tepi putih di sekeliling huruf (teks narasi di atas langit/gambar). Kalau tidak ikut
    dihapus, sisa tepi putihnya jadi noda putih berbentuk huruf."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    r = max(2, int(round(lh * 0.35)))
    near = cv2.dilate(tm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    outer = cv2.dilate(near, np.ones((9, 9), np.uint8), iterations=2) & ~near
    ov = gray[outer > 0]
    if ov.size and np.median(ov) >= 240:
        return np.zeros_like(tm)        # latarnya sendiri putih (balon): tidak ada tepi putih terpisah
    bright = ((gray >= 225) & (near > 0) & (tm == 0)).astype(np.uint8)
    if not bright.any():
        return np.zeros_like(tm)
    # hanya piksel terang yang menempel ke huruf
    seed = cv2.dilate(tm, np.ones((3, 3), np.uint8)) & (bright * 255)
    n, lbl = cv2.connectedComponents(bright)
    ids = np.unique(lbl[seed > 0])
    halo = np.isin(lbl, ids[ids > 0]).astype(np.uint8) * 255
    return cv2.dilate(halo, np.ones((3, 3), np.uint8))


def _flat_background(img: np.ndarray, mask: np.ndarray, inside: np.ndarray | None = None):
    """Warna latar bila sekitar teks polos (mis. putih balon); None bila bertekstur/bergambar.
    inside: bagian dalam balon -- garis balon & raster DI LUAR balon tidak ikut dinilai (teks yang
    rapat ke tepi balon tetap dianggap di latar polos)."""
    ring = cv2.dilate(mask, np.ones((7, 7), np.uint8), iterations=2) & ~mask
    if inside is not None:
        r2 = ring & inside
        if (r2 > 0).sum() >= 30:
            ring = r2
    vals = img[ring > 0]
    if vals.size < 30:
        return None
    gray = vals.mean(axis=1)
    med = float(np.median(gray))
    # hanya latar yang benar-benar rata (putih balon; sedikit garis balon di dekatnya boleh);
    # gradasi / balon transparan -> generate ulang
    if med > 150 and (np.abs(gray - med) <= 6).mean() >= 0.9 and np.percentile(gray, 95) - np.percentile(gray, 30) < 12:
        return np.median(vals[np.abs(gray - med) <= 6], axis=0).astype(np.uint8)
    return None


def _grainy(patch: np.ndarray) -> bool:
    """Patch bertekstur halus acak (raster / bintik), bukan gambar bergaris besar."""
    g = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    if g.std() < 6:
        return False
    dark = (g < 128).astype(np.uint8)
    n, _l, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    if n <= 1:
        return True
    big = st[1:, 4] > max(30, g.size * 0.02)
    return big.sum() <= 1


def _grain_sample(img: np.ndarray, mask: np.ndarray, inside: np.ndarray | None = None, loose: bool = False,
                  lh: float = 0.0):
    """Piksel latar di sekitar teks bila latarnya berbintik (std > 3); None bila benar-benar polos.
    loose=True: untuk balon terang bertekstur -- None bila latarnya ternyata gambar (bukan butiran)."""
    ring = cv2.dilate(mask, np.ones((9, 9), np.uint8), iterations=2) & ~cv2.dilate(mask, np.ones((3, 3), np.uint8))
    if inside is not None:
        r2 = ring & inside
        if (r2 > 0).sum() >= 60:
            ring = r2
    vals = img[ring > 0]
    if len(vals) < 60:
        return None
    g = vals.mean(axis=1)
    med = float(np.median(g))
    keep = vals[np.abs(g - med) <= 40]          # tanpa garis balon / huruf yang tersisa
    if loose:
        # bintik gelap KECIL (raster) bagian dari butiran; hanya coretan gelap besar yang dibuang
        # (hanya untuk latar raster kasar; balon putih biasa tetap seperti semula)
        gimg = img.mean(axis=2) if img.ndim == 3 else img.astype(float)
        if _coarse_grain(gimg.astype(np.float32), ring):
            dark = ((gimg < med - 40) & (ring > 0)).astype(np.uint8)
            n, lbl, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
            thr = max(14, int((lh * 0.22) ** 2)) if lh else 14
            big = np.zeros(n, bool)
            big[1:] = st[1:, 4] > thr
            vals2 = img[(ring > 0) & ~big[lbl]]
            if len(vals2) >= 60:
                keep = vals2
        # butiran halus: latar terang dan hampir semua piksel dekat dengan nilai tengahnya
        if med < 175 or len(keep) < 0.85 * len(vals):
            return None
        return keep if len(keep) >= 60 else None
    if len(keep) < 60 or float(keep.mean(axis=1).std()) <= 3.0:
        return None
    return keep


def _coarse_grain(gray: np.ndarray, clean: np.ndarray) -> bool:
    """Latar raster / bintik kasar: banyak titik gelap KECIL tersebar (bukan garis / huruf besar)."""
    c = clean > 0
    if c.sum() < 200:
        return False
    med = float(np.median(gray[c]))
    dark = ((gray < med - 50) & c).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    if n <= 1:
        return False
    small = st[1:, 4] <= 14
    return float(st[1:, 4][small].sum()) > 0.03 * c.sum()


def _quilt_fill(dst: np.ndarray, fill: np.ndarray, src: np.ndarray, clean: np.ndarray, seed: int = 0,
               k: int = 8, ref: float | None = None, tol: float = 22.0) -> bool:
    """Isi piksel `fill` dengan potongan kecil kxk yang diambil ACAK dari latar bersih di sekitarnya
    (clean). Bintik raster / butiran kertas tetap utuh polanya tanpa pola berulang, dan kecerahannya
    sama dengan latar di sekitar teks. ref = kecerahan latar yang diinginkan (opsional)."""
    clean = (clean > 0).astype(np.uint8)
    # jangan ambil potongan yang berisi coretan gelap besar (garis bata, garis balon, sisa huruf):
    # hanya butiran / bintik kecil yang disalin, supaya tidak muncul potongan garis berserakan
    gsrc = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
    dark = (gsrc < 110).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    if n > 1:
        big = np.zeros(n, bool)
        big[1:] = (st[1:, 4] > max(16, k * 2)) | (np.maximum(st[1:, 2], st[1:, 3]) > k)
        clean &= ~cv2.dilate(big[lbl].astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    ok = cv2.erode(clean, np.ones((k, k), np.uint8), anchor=(0, 0), borderType=cv2.BORDER_CONSTANT,
                   borderValue=0)
    H, W = clean.shape
    ok[H - k + 1:, :] = 0
    ok[:, W - k + 1:] = 0
    if ref is not None:
        g = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY).astype(np.float32)
        mean = cv2.boxFilter(g, -1, (k, k), anchor=(0, 0), normalize=True, borderType=cv2.BORDER_REPLICATE)
        ok &= (np.abs(mean - ref) <= tol).astype(np.uint8)
    cy, cx = np.nonzero(ok)
    if cy.size < 20:
        return False
    ys, xs = np.nonzero(fill)
    if ys.size == 0:
        return True
    rng = np.random.default_rng(seed)
    y0, x0 = int(ys.min()), int(xs.min())
    # setiap sel kxk di area isi mendapat sumber acak sendiri
    cell = ((ys - y0) // k) * 100000 + (xs - x0) // k
    uniq, inv = np.unique(cell, return_inverse=True)
    pick = rng.integers(0, cy.size, uniq.size)
    sy, sx = cy[pick][inv] + (ys - y0) % k, cx[pick][inv] + (xs - x0) % k
    dst[ys, xs] = src[sy, sx]
    return True


def _outline_only(inside: np.ndarray, stm: np.ndarray, lh: float) -> bool:
    """Area 'balon' hampir seluruhnya hanya huruf + tepi putih tipisnya (tidak ada ruang balon)."""
    A = int((inside > 0).sum())
    if A < 50:
        return False
    r = max(2, int(lh * 0.6))
    band = cv2.dilate(stm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2))
    free = int(((inside > 0) & (band == 0)).sum())
    return free < 0.15 * A


def _line_mask(gray: np.ndarray, lh: float, thr: int = 160) -> np.ndarray:
    """Garis panjang (tepi balon, tepi kotak narasi, garis gambar) -- termasuk garis tipis / abu-abu
    hasil antialias. Ruas lurus yang lebih panjang dari tinggi huruf dicari dengan 'opening' berbentuk
    garis di 12 arah; huruf tidak punya ruas lurus sepanjang itu, jadi huruf yang menempel ke garis
    tidak ikut terhitung sebagai garis."""
    dark = (gray < thr).astype(np.uint8)
    L = max(9, int(lh * 1.0)) | 1
    out = np.zeros_like(dark)
    c = L // 2
    for ang in range(0, 180, 15):
        k = np.zeros((L, L), np.uint8)
        dx, dy = np.cos(np.radians(ang)) * c, np.sin(np.radians(ang)) * c
        cv2.line(k, (int(round(c - dx)), int(round(c - dy))), (int(round(c + dx)), int(round(c + dy))), 1, 1)
        out |= cv2.morphologyEx(dark, cv2.MORPH_OPEN, k)
    return out > 0


def _letters_on_lines(lbl, ids, stm, lh):
    """Bagian huruf yang menempel ke garis panjang (tepi balon / kotak) di dekat teks. Garis = ruas
    lurus yang lebih panjang dari tinggi huruf (dicari dengan 'opening' berbentuk garis di 12 arah);
    sisanya di dalam area teks = huruf."""
    ys, xs = np.nonzero(stm)
    if ys.size == 0 or len(ids) == 0:
        return None
    H, W = stm.shape
    m = int(lh * 0.6)
    x0, y0 = max(0, xs.min() - m), max(0, ys.min() - m)
    x1, y1 = min(W, xs.max() + m + 1), min(H, ys.max() + m + 1)
    pad = int(lh * 1.5)
    X0, Y0, X1, Y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
    mask = np.isin(lbl[Y0:Y1, X0:X1], ids).astype(np.uint8)
    if not mask.any():
        return None
    L = max(7, int(lh * 0.9)) | 1        # ruas pendek: garis balon yang melengkung tetap terbaca garis
    linepix = np.zeros_like(mask)
    for ang in range(0, 180, 15):
        k = np.zeros((L, L), np.uint8)
        c = L // 2
        dx, dy = np.cos(np.radians(ang)) * c, np.sin(np.radians(ang)) * c
        cv2.line(k, (int(round(c - dx)), int(round(c - dy))), (int(round(c + dx)), int(round(c + dy))), 1, 1)
        linepix |= cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    linepix = cv2.dilate(linepix, np.ones((3, 3), np.uint8))
    cand = (mask > 0) & (linepix == 0)
    win = np.zeros_like(cand)
    win[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0] = True
    cand &= win
    n, l2, st, _ = cv2.connectedComponentsWithStats(cand.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, 4] >= 6
    cand = keep[l2]
    if not cand.any():
        return None
    out = np.zeros(stm.shape, bool)
    out[Y0:Y1, X0:X1] = cand
    return out


def _outline_text_fill(dst, sub, stm, lh, seed, ai_sub, detail_sub) -> bool:
    """Teks bergaris tepi putih di atas raster / gambar: huruf + tepi putihnya diganti latar dari
    LUAR tepi. Latar berbintik rata -> diisi tekstur aslinya langsung (tanpa AI, rapi & cepat).
    Latar dengan garis / gambar (dinding bata, dsb.) -> bentuknya dibuat ulang AI, lalu butiran
    rasternya ditambahkan kembali supaya tidak terlihat kabur. False = tidak bisa (pakai cara biasa)."""
    gray = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    r = max(2, int(round(lh * 0.35)))
    band = cv2.dilate(stm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2))
    # tepi putih bisa lebih tebal: ikutkan piksel terang yang menempel ke pita huruf
    bright = (gray >= 215).astype(np.uint8)
    n, lbl = cv2.connectedComponents(bright)
    ids = np.unique(lbl[(band > 0) & (bright > 0)])
    reach = cv2.dilate(stm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(lh * 0.8) + 1,) * 2))
    halo = np.isin(lbl, ids[ids > 0]) & (reach > 0)
    full = cv2.dilate(((band > 0) | halo).astype(np.uint8), np.ones((3, 3), np.uint8))
    # garis panjang (tepi kotak narasi / balon, garis gambar) yang bukan huruf: tidak boleh ditimpa,
    # dan menjadi pembatas -- tekstur hanya diambil dari ruang yang sama dengan teks
    dark = (gray < 110).astype(np.uint8)
    n, dl, dst_, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    over = np.bincount(dl[stm > 0], minlength=n)
    big = (dst_[:, 4] > max(30, int((lh * 0.5) ** 2))) & \
        (np.maximum(dst_[:, 2], dst_[:, 3]) > lh * 1.6) & (over < 0.3 * dst_[:, 4])
    big[0] = False
    lines = big[dl] & (stm == 0)          # huruf yang menempel ke garis tetap ikut dihapus
    stuck = _letters_on_lines(dl, np.nonzero(big)[0], stm, lh)
    if stuck is not None:                 # huruf yang menempel ke garis balon / kotak
        lines &= ~stuck
    # garis tipis / abu-abu (antialias) yang menyambung garis tebal juga dilindungi
    lmask = _line_mask(gray, lh) & (stm == 0)
    if stuck is not None:
        lmask &= ~stuck
    lines |= cv2.dilate(lmask.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    lines &= (stm == 0)
    full = (full > 0) & ~lines
    if stuck is not None:
        full |= (cv2.dilate(stuck.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0) & ~lines
    barrier = cv2.dilate((big[dl] | lmask).astype(np.uint8), np.ones((3, 3), np.uint8))
    nf, fl = cv2.connectedComponents((barrier == 0).astype(np.uint8), connectivity=4)
    seeds = fl[(stm > 0) & (barrier == 0)]
    if seeds.size:
        cnt = np.bincount(seeds, minlength=nf)
        cnt[0] = 0
        main = cnt >= max(1, 0.35 * cnt.max())     # ruang tempat sebagian besar huruf berada
        region = main[fl]
        # isi tidak boleh menyeberangi garis (mis. ke balon putih di sebelah kotak narasi)
        full = full & (region | (stm > 0) | (barrier > 0) & ~lines)
    else:
        region = np.ones_like(full)
    full = full.astype(np.uint8)
    ring = cv2.dilate(full, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (4 * int(lh) + 1,) * 2)) & ~full
    ring2 = (ring > 0) & region & (barrier == 0)
    if ring2.sum() >= 300:
        ring = ring2.astype(np.uint8)
    rv = gray[ring > 0]
    if rv.size < 100:
        return False
    if (np.median(rv) >= 235 and (rv >= 225).mean() > 0.9) or not _coarse_grain(gray, ring):
        return False                                   # latarnya polos / bukan raster: cara biasa
    k = max(4, min(8, int(lh * 0.3)))
    q = sub.copy()
    if not _quilt_fill(q, full > 0, sub.copy(), ring > 0, seed, k=k, ref=float(rv.mean()), tol=30.0):
        return False
    # latar yang sebagian besar gambar (bukan butiran raster) -> biarkan AI yang membuat ulang
    dark = (gray < 110).astype(np.uint8) & (ring > 0).astype(np.uint8)
    nn, l2, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    big = sum(int(a) for a in st[1:, 4] if a > max(16, k * 2))
    if big > 0.25 * rv.size:
        return False
    m = full > 0
    dst[m] = q[m]
    return True


def _solid_white_far(sub: np.ndarray, stm: np.ndarray, halo: np.ndarray, lh: float) -> float:
    """Berapa banyak putih POLOS yang menyambung ke tepi putih huruf tapi jauh dari huruf
    (dibanding jumlah piksel huruf). Besar = teks di atas kotak / pulau putih (bagian desain);
    kecil = hanya garis tepi putih di sekeliling huruf."""
    gray = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    k = max(3, int(lh * 0.18)) | 1
    solid = cv2.morphologyEx((gray >= 225).astype(np.uint8), cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    n, lbl = cv2.connectedComponents(solid)
    ids = np.unique(lbl[(halo > 0) & (solid > 0)])
    ids = ids[ids > 0]
    if not ids.size:
        return 0.0
    reg = np.isin(lbl, ids)
    d = cv2.distanceTransform((stm == 0).astype(np.uint8), cv2.DIST_L2, 3)
    far = int((reg & (d > lh * 0.7)).sum())
    return far / max(1, int((stm > 0).sum()))


def _fill_bubble(img, b):
    # bagian dalam balon (tanpa garis tepi) diisi warna dominan latar balon
    shrink = max(4, int(min(b.w, b.h) * 0.035)) if b.mask_poly else 0
    inner = block_region_mask(img.shape, b, shrink=shrink)
    vals = img[inner > 0]
    if vals.size == 0:
        return
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)[inner > 0]
    light = vals[gray >= np.percentile(gray, 60)]
    color = np.median(light if len(light) else vals, axis=0).astype(np.uint8)
    txt = contrast_mask(img, inner, dilate=0)
    # buang sisa garis tepi: komponen PANJANG yang menempel batas area dalam.
    # Coretan kecil yang menempel (tanda hubung, titik, ujung huruf) tetap dianggap teks.
    border = inner - cv2.erode(inner, np.ones((3, 3), np.uint8), iterations=2)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(txt)
    long_px = max(12, int(min(b.w, b.h) * 0.22))
    for i in np.unique(lbl[(border > 0) & (txt > 0)]):
        if i and max(st[i][2], st[i][3]) >= long_px:
            txt[lbl == i] = 0
    txt = cv2.dilate(txt, np.ones((3, 3), np.uint8), iterations=2)
    # isi seluruh area teks + sedikit margin, tetap di dalam balon
    ys, xs = np.nonzero(txt)
    if len(xs) == 0:
        return
    zone = np.zeros_like(inner)
    pad = 4
    cv2.rectangle(zone, (int(xs.min()) - pad, int(ys.min()) - pad), (int(xs.max()) + pad, int(ys.max()) + pad), 255, -1)
    zone = cv2.bitwise_and(zone, inner)
    img[zone > 0] = color


def _safe_contrast_mask(img, region):
    """Cadangan bila huruf tidak terdeteksi: piksel kontras, TANPA garis panjang yang menyentuh tepi
    area (garis balon / gambar), supaya balon tidak ikut terhapus."""
    txt = contrast_mask(img, region, dilate=0)
    border = region - cv2.erode(region, np.ones((3, 3), np.uint8), iterations=2)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(txt)
    ys, xs = np.nonzero(region)
    rh = (ys.max() - ys.min()) if ys.size else 1
    drop = np.zeros(n, bool)
    for i in set(np.unique(lbl[(border > 0) & (txt > 0)])) | {i for i in range(1, n) if st[i][3] > rh * 0.5}:
        drop[i] = True
    drop[0] = True
    txt = (~drop[lbl]).astype(np.uint8) * 255 & txt
    return cv2.dilate(txt, np.ones((3, 3), np.uint8), iterations=2)


def _inpaint_opencv(img, mask):
    """Telea, dikerjakan per kelompok area (potongan kecil) -- hasil sama dengan seluruh halaman,
    tapi jauh lebih cepat & hemat memori di halaman besar (webtoon)."""
    H, W = mask.shape[:2]
    if H * W < 600_000:
        return cv2.inpaint(img, mask, 7, cv2.INPAINT_TELEA)
    grouped = cv2.dilate(mask, np.ones((25, 25), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(grouped, connectivity=8)
    if n <= 1:
        return img.copy()
    if st[1:, 4].sum() > 0.35 * H * W:
        return cv2.inpaint(img, mask, 7, cv2.INPAINT_TELEA)
    out = img.copy()
    pad = 16
    for i in range(1, n):
        x, y, w, h, _a = st[i]
        x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)
        m = mask[y0:y1, x0:x1].copy()
        m[lbl[y0:y1, x0:x1] != i] = 0
        if not m.any():
            continue
        res = cv2.inpaint(np.ascontiguousarray(img[y0:y1, x0:x1]), m, 7, cv2.INPAINT_TELEA)
        sel = m > 0
        out[y0:y1, x0:x1][sel] = res[sel]
    return out


def _inpaint_lama(img, mask):
    """LaMa per area teks (potongan dengan konteks di sekitarnya), lalu HANYA piksel yang dihapus
    yang ditempel balik. Lebih rapi (LaMa dilatih di gambar ±512 px) dan bagian lain halaman
    tidak ikut berubah. Bila LaMa gagal (mis. model belum terunduh) -> OpenCV."""
    from PIL import Image
    try:
        lama = _get_lama()
    except Exception:
        return _inpaint_opencv(img, mask)
    H, W = mask.shape
    out = img.copy()
    # kelompokkan area yang berdekatan supaya tidak memanggil LaMa berkali-kali
    grouped = cv2.dilate(mask, np.ones((25, 25), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(grouped, connectivity=8)
    for i in range(1, n):
        x, y, w, h, _a = st[i]
        pad = max(48, int(max(w, h) * 0.6))
        x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)
        m = mask[y0:y1, x0:x1].copy()
        m[lbl[y0:y1, x0:x1] != i] = 0
        if not m.any():
            continue
        crop = out[y0:y1, x0:x1]
        ch, cw = crop.shape[:2]
        scale = min(1.0, float(LAMA_MAX_SIDE) / max(ch, cw))   # potongan raksasa: kecilkan dulu
        src, mm = crop, m
        if scale < 1.0:
            size = (max(8, int(cw * scale)), max(8, int(ch * scale)))
            src = cv2.resize(crop, size, interpolation=cv2.INTER_AREA)
            mm = (cv2.resize(m, size, interpolation=cv2.INTER_NEAREST) > 0).astype(np.uint8) * 255
            mm = cv2.dilate(mm, np.ones((3, 3), np.uint8))
        try:
            res = lama(Image.fromarray(cv2.cvtColor(src, cv2.COLOR_BGR2RGB)), Image.fromarray(mm))
        except Exception:
            out[y0:y1, x0:x1] = _inpaint_opencv(crop, m)
            continue
        res = cv2.cvtColor(np.array(res), cv2.COLOR_RGB2BGR)[: src.shape[0], : src.shape[1]]
        if scale < 1.0:
            res = cv2.resize(res, (cw, ch), interpolation=cv2.INTER_CUBIC)
        # tepi lembut 1–2 px supaya sambungan tidak terlihat
        alpha = cv2.GaussianBlur(cv2.dilate(m, np.ones((3, 3), np.uint8)), (5, 5), 0).astype(np.float32)[..., None] / 255.0
        alpha[m > 0] = 1.0
        out[y0:y1, x0:x1] = (res * alpha + crop * (1 - alpha)).astype(np.uint8)
    return out


def clean_page(img: np.ndarray, blocks: list[TextBlock], method: str = "auto", base=None,
               patch: bool = False, lines: bool = False) -> np.ndarray:
    """img = halaman asli (sumber deteksi huruf). base = gambar awal hasil (mis. hasil bersih lama yang
    sebagian dikembalikan ke asli); default salinan img."""
    out = img.copy() if base is None else base.copy()
    use_lama = lama_available()
    wants_lama0 = use_lama and method in ("lama", "auto")
    detail = np.zeros(img.shape, np.int16)      # butiran raster yang ditambahkan setelah AI
    ai_mask = np.zeros(img.shape[:2], np.uint8)
    cands = None
    done = []            # (blok, mask huruf, tinggi huruf) untuk tahap perapian

    for b in blocks:
        b._grain_fill = False
        if not b.clean or b.kind == "title":      # logo judul diurus titlelogo
            continue
        if b.text_rect and not (b.source or "").strip() and not (b.translation or "").strip():
            continue        # hasil deteksi yang tidak terbaca (mis. SFX/gambar): jangan dihapus
        if getattr(b, "sfx", False):
            if (b.translation or "").strip() == (b.source or "").strip():
                continue        # SFX yang tidak diterjemahkan (mis. "!!") dibiarkan apa adanya
            from .sfx import sfx_mask
            tm = sfx_mask(img, b)
            if tm is not None:
                ai_mask |= tm | _halo(img, tm, float(b.src_h or 20) * 0.25)
                continue
        region = block_region_mask(img.shape, b)
        if b.kind != "bubble" and text_polarity(img, region)[0] == "light":
            ai_mask |= text_pixel_mask(img, region, dilate=3)       # huruf putih bergaris tepi
            continue
        # hanya HURUF yang dihapus; garis balon & gambar di sekitarnya tidak disentuh
        if cands is None:
            cands = page_letters(img)          # sekali per halaman
        tm, _lh = text_only_mask(img, b, cands)
        if tm is None:
            # huruf tidak dikenali: tetap hanya piksel kontras (tanpa garis balon), lalu generate
            # ulang latarnya -- jangan menempel kotak putih yang menutupi balon / gambar
            ai_mask |= _safe_contrast_mask(img, region)
            continue
        done.append((b, tm, _lh))
        # kerjakan hanya di sekitar blok (halaman webtoon bisa >10.000 px tingginya)
        H_, W_ = img.shape[:2]
        e = int(max(40, _lh * 3))
        rx0, ry0 = max(0, int(b.x) - e), max(0, int(b.y) - e)
        rx1, ry1 = min(W_, int(b.x + b.w) + e), min(H_, int(b.y + b.h) + e)
        sub, stm = img[ry0:ry1, rx0:rx1], tm[ry0:ry1, rx0:rx1]
        inside = None
        if b.kind == "bubble" and b.mask_poly:
            sh = max(2, int(min(b.w, b.h) * 0.012))
            inside = block_region_mask(img.shape, b, shrink=sh)[ry0:ry1, rx0:rx1]
            if _outline_only(inside, stm, _lh):
                # "balon" yang terdeteksi ternyata hanya garis tepi putih di sekeliling huruf
                # (teks bergaris tepi di atas raster / gambar, mis. "Just between us..."):
                # latar aslinya ada di LUAR tepi putih itu
                inside = None
                if method in ("auto", "fill") and _outline_text_fill(
                        out[ry0:ry1, rx0:rx1], sub, stm, _lh, int(b.x) * 31 + int(b.y),
                        ai_mask[ry0:ry1, rx0:rx1], detail[ry0:ry1, rx0:rx1]):
                    b._grain_fill = True
                    continue
        color = _flat_background(sub, stm, inside) if method in ("auto", "fill") else None
        if color is None and inside is not None and method in ("auto", "fill"):
            grain = _grain_sample(sub, stm, inside, loose=True, lh=_lh)
            if grain is not None:
                # balon terang berbintik (tekstur kertas / raster): isi dengan TEKSTUR latarnya sendiri
                # (potongan latar bersih ditempel berulang) -> bintik gelap & terang tetap sama polanya,
                # bekas teks tidak terlihat sebagai tambalan yang lebih terang / halus
                # huruf + garis tepi putih tipis di sekelilingnya (kalau tidak ikut diganti, tepi
                # putihnya tertinggal sebagai bayangan huruf yang lebih terang)
                rr = max(2, int(round(_lh * 0.22)))
                band = cv2.dilate(stm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rr + 1,) * 2))
                fillm = (band > 0) & (inside > 0)
                clean = (cv2.dilate(band, np.ones((5, 5), np.uint8)) == 0) & \
                    (cv2.erode(inside, np.ones((5, 5), np.uint8)) > 0)
                gsub = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
                cv_ = gsub[clean]
                ref = float(cv_.mean()) if cv_.size > 200 else None
                coarse = cv_.size > 200 and _coarse_grain(gsub, clean)    # raster / bintik kasar
                seed = int(b.x) * 7919 + int(b.y)
                if not coarse:
                    fillm = (cv2.dilate(stm, np.ones((3, 3), np.uint8)) > 0) & (inside > 0)
                if not coarse or not _quilt_fill(out[ry0:ry1, rx0:rx1], fillm, sub.copy(), clean, seed,
                                                 k=max(4, min(8, int(_lh * 0.3))), ref=ref, tol=25.0):
                    rng = np.random.default_rng(seed)
                    out[ry0:ry1, rx0:rx1][fillm] = grain[rng.integers(0, len(grain), int(fillm.sum()))]
                b._grain_fill = True
                rest = (stm > 0) & ~fillm
                if rest.any():
                    ai_mask[ry0:ry1, rx0:rx1] |= rest.astype(np.uint8) * 255
                continue
        if color is not None:
            # sisa tepi samar (antialias / JPEG) di sekitar huruf ikut diratakan
            r2 = max(3, int(round(_lh * 0.3)))
            band = cv2.dilate(stm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r2 + 1,) * 2)) & ~stm
            diff = np.abs(sub.astype(np.int16) - np.asarray(color, np.int16)).max(axis=2)
            halo = (band > 0) & (diff > 5) & (diff < 90)
            fillm = (stm > 0) | halo
            if inside is not None:
                fillm &= inside > 0                                  # jangan menimpa garis balon
            grain = _grain_sample(sub, stm, inside)
            if grain is not None:
                # latar berbintik halus (kertas / raster sangat tipis): isi dengan butiran yang sama,
                # bukan warna rata -> bekas teks tidak terlihat sebagai tambalan polos
                rng = np.random.default_rng(int(b.x) * 7919 + int(b.y))
                k = int(fillm.sum())
                out[ry0:ry1, rx0:rx1][fillm] = grain[rng.integers(0, len(grain), k)]
            else:
                out[ry0:ry1, rx0:rx1][fillm] = color         # latar polos: isi warna latar
            rest = (stm > 0) & ~fillm                                # bagian huruf di luar balon
            if rest.any():
                ai_mask[ry0:ry1, rx0:rx1] |= rest.astype(np.uint8) * 255
        else:
            halo = _halo(sub, stm, _lh)
            hs, ts = int((halo > 0).sum()), int((stm > 0).sum())
            if not getattr(b, "sfx", False) and ts and hs > 0.8 * ts \
                    and (_solid_white_far(sub, stm, halo, _lh) > 1.5 or not wants_lama0):
                # tanpa AI (LaMa tidak ada / metode OpenCV): area besar tidak bisa dibuat ulang dengan
                # rapi, jadi tepi putih tebalnya dipertahankan
                # teks di atas kotak / pulau putih POLOS yang lebar (bagian desain): isi bekas huruf
                # dengan putih itu
                pick = sub[(halo > 0) & (stm == 0)]
                if len(pick):
                    col = np.median(pick, axis=0).astype(np.uint8)
                    fillm = cv2.dilate(stm, np.ones((3, 3), np.uint8)) > 0
                    out[ry0:ry1, rx0:rx1][fillm] = col
                    continue
            # latar bergambar (termasuk teks bergaris tepi putih, mis. "Just between us..." di atas
            # dinding bata): huruf + garis tepi putihnya dihapus dan latarnya dibuat ulang
            full = stm | halo
            if (halo > 0).any():
                full = cv2.dilate(full, np.ones((3, 3), np.uint8))
            if not wants_lama0 and method in ("auto", "fill"):
                # tanpa AI: tempel tekstur latar di sekitarnya (raster / bintik) daripada dioles kabur
                avoid = cv2.dilate(full, np.ones((7, 7), np.uint8))
                ring = cv2.dilate(avoid, np.ones((15, 15), np.uint8)) & ~avoid
                gsub = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
                rv = gsub[ring > 0]
                if rv.size > 100 and rv.std() > 25 and _grainy(sub[ring.any(axis=1)][:, ring.any(axis=0)]):
                    if _quilt_fill(out[ry0:ry1, rx0:rx1], full > 0, sub.copy(), avoid == 0,
                                   int(b.x) * 31 + int(b.y), k=max(4, min(8, int(_lh * 0.3))),
                                   ref=float(rv.mean()), tol=30.0):
                        b._grain_fill = True
                        continue
            ai_mask[ry0:ry1, rx0:rx1] |= full   # generate ulang (AI)

    wants_lama = use_lama and method in ("lama", "auto")
    if ai_mask.any():
        out = _inpaint_lama(out, ai_mask) if wants_lama else _inpaint_opencv(out, ai_mask)
        dm = detail.any(axis=2) & (ai_mask > 0)
        if dm.any():     # AI membuat ulang bentuk latar (garis bata dsb.), butiran raster ditambahkan lagi
            out[dm] = np.clip(out[dm].astype(np.int16) + detail[dm], 0, 255).astype(np.uint8)
    if done and method != "none":
        out = refine_clean(img, out, done, wants_lama)
    if patch and method != "none":
        # 5. periksa kemulusan hasil; area yang belum rapi ditambal dengan area serupa (Patch Tool)
        try:
            from . import patchfill, perf
            rects = [(b.x, b.y, b.w, b.h) for b in blocks if b.clean and b.kind != "title"]
            keep = [(b.x, b.y, b.w, b.h) for b in blocks if not b.clean]
            out = patchfill.auto_patch(img, out, regions=rects, avoid_rects=keep, low_end=perf.low_end())
        except Exception:
            pass
    if lines and method != "none" and done:
        # 6. garis balon / garis gambar yang terputus karena ikut terhapus -> disambung ulang
        #    (seperti memakai pen tool + alat garis: ikuti arah, tebal & warna garis aslinya)
        try:
            from . import linefix
            lh_med = float(np.median([d[2] for d in done]))
            tmask = np.zeros(img.shape[:2], np.uint8)
            for _b, tm_, _l in done:
                tmask |= tm_
            out = linefix.repair(img, out, [(b.x, b.y, b.w, b.h) for b, _t, _l in done], lh=lh_med,
                                 text_mask=tmask)
        except Exception:
            pass
    return out


def refine_clean(img: np.ndarray, out: np.ndarray, done, wants_lama: bool) -> np.ndarray:
    """Tahap perapian setelah hapus teks pertama (dikerjakan per blok, hanya di sekitar teks):

    2. Pulihkan potongan yang salah: garis balon / gambar (coretan panjang yang menembus jauh
       keluar area teks) yang ikut terhapus dikembalikan dari gambar asli.
    3. Cari sisa teks: coretan gelap yang masih tertinggal di bekas posisi huruf (tepi samar,
       titik, ujung huruf) -> dibuat ulang lagi oleh AI (LaMa) / diisi latar.
    4. Rapikan sambungan: tepi area yang dikembalikan / diperbaiki dihaluskan oleh AI.
    """
    H, W = img.shape[:2]
    gray0 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    residue = np.zeros((H, W), np.uint8)
    out = out.copy()
    for b, tm, lh in done:
        lh = max(4.0, float(lh))
        e = int(lh * 3) + 8
        x0, y0 = max(0, int(b.x) - e), max(0, int(b.y) - e)
        x1, y1 = min(W, int(b.x + b.w) + e), min(H, int(b.y + b.h) + e)
        g0 = gray0[y0:y1, x0:x1]
        t = tm[y0:y1, x0:x1] > 0
        if not t.any():
            continue
        o = out[y0:y1, x0:x1]
        go = cv2.cvtColor(o, cv2.COLOR_BGR2GRAY)
        changed = np.abs(o.astype(np.int16) - img[y0:y1, x0:x1].astype(np.int16)).max(axis=2) > 12

        # --- 2. coretan panjang (garis balon / gambar) yang terpotong -> kembalikan
        dark0 = (g0 < 110).astype(np.uint8)
        n, lbl, st, _ = cv2.connectedComponentsWithStats(dark0, connectivity=8)
        core = cv2.erode(t.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=max(1, int(lh * 0.12)))
        restore = np.zeros_like(t)
        for i in np.unique(lbl[changed & (dark0 > 0)]):
            if i == 0:
                continue
            x, y, w, h, a = st[i]
            comp = lbl == i
            outside = (comp & ~t).sum()
            # coretan panjang yang sebagian besar berada di luar area huruf = bukan huruf
            if max(w, h) > lh * 3.2 and outside > 0.45 * a:
                restore |= comp & changed & (core == 0)
        if restore.any():
            o[restore] = img[y0:y1, x0:x1][restore]
            # 4. sambungan antara bagian yang dikembalikan & bagian yang dibersihkan
            seam = cv2.dilate(restore.astype(np.uint8), np.ones((3, 3), np.uint8)) & changed & ~restore
            if not getattr(b, "_grain_fill", False):          # raster: sambungan sudah bertekstur
                residue[y0:y1, x0:x1] |= seam.astype(np.uint8) * 255

        # --- 3. sisa huruf: masih gelap di tempat yang dulunya huruf, padahal sekitarnya terang
        near = cv2.dilate(t.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        bgv = cv2.medianBlur(go, max(3, int(lh * 0.8)) | 1)
        # garis balon / kotak di dekat huruf bukan sisa huruf (jangan dioles)
        keep_lines = cv2.dilate((_line_mask(go, lh) & ~t).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        left = near & (g0 < 160) & (go.astype(np.int16) < bgv.astype(np.int16) - 45) & ~restore & ~keep_lines
        if left.any():
            nn, l2, s2, _ = cv2.connectedComponentsWithStats(left.astype(np.uint8), connectivity=8)
            # latar berbintik yang diisi tekstur: bintik seukuran butiran bukan sisa huruf
            grainy = getattr(b, "_grain_fill", False)
            min_a = max(14, int((lh * 0.22) ** 2)) if grainy else 3
            loc = np.zeros(left.shape, np.uint8)
            for i in range(1, nn):
                if s2[i][4] >= min_a and max(s2[i][2], s2[i][3]) <= lh * 2.5:
                    loc[l2 == i] = 255
            if loc.any() and grainy:
                # latar raster: sisa huruf diisi tekstur raster juga (dioles AI malah jadi noda kabur)
                fillr = cv2.dilate(loc, np.ones((5, 5), np.uint8)) > 0
                fillr &= ~keep_lines
                clean_src = (cv2.dilate(loc, np.ones((9, 9), np.uint8)) == 0) & ~keep_lines & ~near
                _quilt_fill(o, fillr, o.copy(), clean_src, int(b.x) * 13 + int(b.y),
                            k=max(4, min(8, int(lh * 0.3))), ref=None)
                loc[:] = 0          # tidak dioles AI/Telea (di raster hasilnya noda kabur)
            residue[y0:y1, x0:x1] |= loc
        out[y0:y1, x0:x1] = o
    if residue.any():
        residue = cv2.dilate(residue, np.ones((3, 3), np.uint8))
        out = _inpaint_lama(out, residue) if wants_lama else _inpaint_opencv(out, residue)
    return out
