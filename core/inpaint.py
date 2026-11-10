"""Hapus teks asli (cleaning).

- "fill"   : isi bagian dalam balon dengan warna balon. Cepat & sangat rapi
             untuk balon putih/polos.
- "opencv" : cv2.inpaint (Telea) hanya pada piksel huruf. Cocok untuk teks
             di atas latar sederhana.
- "lama"   : LaMa (AI inpainting) jika paket simple-lama-inpainting terpasang.
             Terbaik untuk teks di atas gambar/arsiran.
- "auto"   : balon -> fill, teks bebas -> lama (jika ada) atau opencv.
"""
from __future__ import annotations

import cv2
import numpy as np

from .models import TextBlock

_lama = None


def _get_lama():
    global _lama
    if _lama is None:
        from simple_lama_inpainting import SimpleLama
        _lama = SimpleLama()
    return _lama


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


def auto_style(img: np.ndarray, b: TextBlock):
    """Teks bebas berhuruf putih (di atas gambar) -> terjemahan putih bergaris tepi hitam."""
    if b.kind == "bubble":
        return
    region = block_region_mask(img.shape, b)
    pol, _, h = text_polarity(img, region)
    if pol == "light":
        b.color, b.stroke_color = "#FFFFFF", "#000000"
        b.stroke_width = max(b.stroke_width, max(2, int(round(h * 0.12))) if h else 3)


def page_letters(img: np.ndarray):
    """Kandidat huruf untuk SELURUH halaman (ukuran huruf dinilai relatif ke halaman, bukan kotak)."""
    from .detector import _letter_candidates
    return _letter_candidates(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))


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
    X0, Y0, X1, Y1 = U[0] - lh * 1.2, U[1] - lh * 0.7, U[2] + lh * 1.2, U[3] + lh * 0.7
    dark = (crop < 150).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    keep = np.zeros(n, bool)
    hs = [lh]
    ix0, iy0, ix1, iy1 = int(max(0, U[0])), int(max(0, U[1])), int(U[2]), int(U[3])
    bg_light = np.median(crop[iy0:iy1, ix0:ix1]) >= 185     # teks di latar terang (balon)
    for i in range(1, n):
        x, y, w, h, a = st[i]
        # coretan gelap yang SELURUHNYA di dalam blok teks = huruf / tanda baca
        # (boleh setinggi ±2,8 baris: huruf yang tersambung antar baris, mis. "g" dengan "k";
        #  lengkungan garis balon yang masuk ke dalam biasanya lebih tinggi lagi)
        if x >= X0 and y >= Y0 and x + w <= X1 and y + h <= Y1 and h <= lh * 2.8:
            keep[i] = True
    # huruf dikelilingi latar terang di semua sisi; garis balon / gambar punya sisi luar yang gelap
    if bg_light:
        for i in np.nonzero(keep)[0]:
            x, y, w, h, a = st[i]
            p = 10
            sx0, sy0, sx1, sy1 = max(0, x - p), max(0, y - p), min(crop.shape[1], x + w + p), min(crop.shape[0], y + h + p)
            comp = (lbl[sy0:sy1, sx0:sx1] == i).astype(np.uint8)
            k3 = np.ones((3, 3), np.uint8)
            # cincin 2–6 px dari coretan (lewati tepi abu-abu antialias), tanpa coretan lain
            ring = (cv2.dilate(comp, k3, iterations=6) > 0) & (cv2.dilate(comp, k3, iterations=2) == 0) \
                & (dark[sy0:sy1, sx0:sx1] == 0)
            if ring.sum() and (crop[sy0:sy1, sx0:sx1][ring] >= 185).mean() < 0.85:
                keep[i] = False
    keep[0] = False
    m = keep[lbl].astype(np.uint8) * 255
    if not m.any():
        return None, 0
    lh = float(np.median(hs))
    r = max(2, int(round(lh * 0.14)))           # tutup juga tepi huruf yang samar (antialias)
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    full = np.zeros((H, W), np.uint8)
    full[y0:y1, x0:x1] = m
    return full, lh


def _flat_background(img: np.ndarray, mask: np.ndarray):
    """Warna latar bila sekitar teks polos (mis. putih balon); None bila bertekstur/bergambar."""
    ring = cv2.dilate(mask, np.ones((7, 7), np.uint8), iterations=2) & ~mask
    vals = img[ring > 0]
    if vals.size < 30:
        return None
    gray = vals.mean(axis=1)
    if gray.std() < 14 and np.percentile(gray, 10) > 150:
        return np.median(vals, axis=0).astype(np.uint8)
    return None


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
    return cv2.inpaint(img, mask, 7, cv2.INPAINT_TELEA)


def _inpaint_lama(img, mask):
    from PIL import Image
    lama = _get_lama()
    rgb = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    res = lama(rgb, Image.fromarray(mask))
    out = cv2.cvtColor(np.array(res), cv2.COLOR_RGB2BGR)
    return out[: img.shape[0], : img.shape[1]]


def clean_page(img: np.ndarray, blocks: list[TextBlock], method: str = "auto") -> np.ndarray:
    out = img.copy()
    use_lama = lama_available()
    ai_mask = np.zeros(img.shape[:2], np.uint8)
    cands = None

    for b in blocks:
        if not b.clean:
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
            if b.kind == "bubble":
                _fill_bubble(out, b)                                 # cadangan lama
            else:
                ai_mask |= _safe_contrast_mask(img, region)
            continue
        color = _flat_background(img, tm) if method in ("auto", "fill") else None
        if color is not None:
            out[tm > 0] = color                                      # latar polos: isi warna latar
        else:
            ai_mask |= tm                                            # latar bergambar: generate ulang (AI)

    if ai_mask.any():
        wants_lama = use_lama and method in ("lama", "auto")
        out = _inpaint_lama(out, ai_mask) if wants_lama else _inpaint_opencv(out, ai_mask)
    return out
