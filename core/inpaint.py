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
    return cv2.inpaint(img, mask, 5, cv2.INPAINT_TELEA)


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
