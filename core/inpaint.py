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


def text_pixel_mask(img: np.ndarray, region: np.ndarray, dilate: int = 3) -> np.ndarray:
    """Piksel huruf = piksel yang kontras dengan latar di dalam region."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    vals = gray[region > 0]
    if vals.size == 0:
        return np.zeros_like(region)
    bg = np.median(vals)
    if bg > 127:   # latar terang, huruf gelap
        txt = (gray < bg - 60).astype(np.uint8) * 255
    else:          # latar gelap, huruf terang
        txt = (gray > bg + 60).astype(np.uint8) * 255
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
    if letters.any():
        if pol == "light":
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
        else:
            txt = cv2.dilate(letters, np.ones((3, 3), np.uint8), iterations=max(1, dilate))
        return cv2.bitwise_and(txt, cv2.dilate(region, np.ones((3, 3), np.uint8)))
    # cadangan: kontras terhadap median latar
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


def auto_style(img: np.ndarray, b: TextBlock):
    """Teks bebas berhuruf putih (di atas gambar) -> terjemahan putih bergaris tepi hitam."""
    if b.kind == "bubble":
        return
    region = block_region_mask(img.shape, b)
    pol, _, h = text_polarity(img, region)
    if pol == "light":
        b.color, b.stroke_color = "#FFFFFF", "#000000"
        b.stroke_width = max(b.stroke_width, max(2, int(round(h * 0.12))) if h else 3)


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
    txt = text_pixel_mask(img, inner, dilate=0)
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

    for b in blocks:
        if not b.clean:
            continue
        m = method
        if m == "auto":
            m = "fill" if b.kind == "bubble" else ("lama" if use_lama else "opencv")
        if m == "fill":
            _fill_bubble(out, b)
        else:
            region = block_region_mask(img.shape, b)
            ai_mask |= text_pixel_mask(img, region, dilate=3)

    if ai_mask.any():
        wants_lama = use_lama and method in ("lama", "auto")
        out = _inpaint_lama(out, ai_mask) if wants_lama else _inpaint_opencv(out, ai_mask)
    return out
