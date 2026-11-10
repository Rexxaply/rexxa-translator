"""Gradasi warna teks ala Photoshop.

Jenis (TextBlock.grad_type):
  linear    : warna 1 -> warna 2 searah sudut (grad_angle; 90 = atas -> bawah, 0 = kiri -> kanan)
  reflected : warna 1 di tengah, warna 2 di kedua ujung (cermin)
  radial    : oval: warna 1 di tengah, warna 2 di tepi (oval mengikuti bentuk area teks)
  split     : pisah 2 warna dengan batas tegas (posisi batas = grad_pos, kehalusan = grad_soft)
Posisi (grad_pos 0..1)  : titik tengah peralihan warna (0.5 = di tengah).
Kehalusan (grad_soft 0..1): lebar peralihan; 1 = halus penuh, 0 = garis tegas.
Cakupan (grad_scope)    : "block" = satu gradasi untuk seluruh teks, "line" = berulang tiap baris.
"""
from __future__ import annotations

import math

import numpy as np

TYPES = [("linear", "Linear"), ("reflected", "Cermin (reflected)"), ("radial", "Oval (radial)"),
         ("split", "Pisah 2 warna")]


def field(w: int, h: int, kind: str = "linear", angle: float = 90.0, pos: float = 0.5,
          soft: float = 1.0) -> np.ndarray:
    """Nilai 0..1 (0 = warna 1, 1 = warna 2) untuk kotak w x h."""
    w, h = max(1, int(w)), max(1, int(h))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (xs + 0.5) / w - 0.5           # -0.5..0.5
    v = (ys + 0.5) / h - 0.5
    if kind == "radial":
        t = np.sqrt((u / 0.5) ** 2 + (v / 0.5) ** 2) / math.sqrt(2) * 1.25
        t = np.clip(t, 0, 1)
    else:
        a = math.radians(angle)
        dx, dy = math.cos(a), math.sin(a)          # sudut 90 = arah ke bawah (koordinat layar)
        proj = u * dx + v * dy
        ext = 0.5 * (abs(dx) + abs(dy)) or 0.5     # proyeksi sudut kotak -> -ext..ext
        t = (proj / ext + 1) / 2                    # 0..1
        if kind == "reflected":
            t = np.abs(t * 2 - 1)
    if kind == "split":
        soft = min(soft, 0.08)
    s = max(1e-3, float(soft))
    p = float(pos)
    t = np.clip((t - (p - s / 2)) / s, 0, 1)
    return t.astype(np.float32)


def colorize(t: np.ndarray, c1, c2) -> np.ndarray:
    """RGBA uint8 dari medan t, c1/c2 = (r, g, b)."""
    c1 = np.asarray(c1, np.float32)
    c2 = np.asarray(c2, np.float32)
    rgb = c1[None, None, :] + (c2 - c1)[None, None, :] * t[..., None]
    a = np.full(t.shape + (1,), 255, np.float32)
    return np.concatenate([rgb, a], axis=2).clip(0, 255).astype(np.uint8)


def css_preview(kind, angle, c1, c2, pos=0.5, soft=1.0) -> str:
    """Gaya Qt (qlineargradient / qradialgradient) untuk tombol pratinjau."""
    lo, hi = max(0.0, pos - soft / 2), min(1.0, pos + soft / 2)
    if kind == "split":
        lo, hi = max(0.0, pos - 0.01), min(1.0, pos + 0.01)
    if kind == "radial":
        return (f"qradialgradient(cx:0.5, cy:0.5, radius:0.6, fx:0.5, fy:0.5, stop:{lo:.2f} {c1}, "
                f"stop:{hi:.2f} {c2})")
    a = math.radians(angle)
    dx, dy = math.cos(a) / 2, math.sin(a) / 2
    x1, y1, x2, y2 = 0.5 - dx, 0.5 - dy, 0.5 + dx, 0.5 + dy
    if kind == "reflected":
        return (f"qlineargradient(x1:{x1:.2f}, y1:{y1:.2f}, x2:{x2:.2f}, y2:{y2:.2f}, "
                f"stop:0 {c2}, stop:{0.5 - hi / 2:.2f} {c2}, stop:{0.5 - lo / 2:.2f} {c1}, "
                f"stop:{0.5 + lo / 2:.2f} {c1}, stop:{0.5 + hi / 2:.2f} {c2}, stop:1 {c2})")
    return (f"qlineargradient(x1:{x1:.2f}, y1:{y1:.2f}, x2:{x2:.2f}, y2:{y2:.2f}, "
            f"stop:{lo:.2f} {c1}, stop:{hi:.2f} {c2})")
