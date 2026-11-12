"""Hapus latar gambar lapisan (chroma key): latar putih, hijau, biru, warna pilihan, atau latar
"transparan palsu" (kotak-kotak abu-abu/putih) yang sering ada di gambar unduhan.

Semua fungsi bekerja di numpy RGBA (urutan R, G, B, A) dan tidak mengubah gambar aslinya."""
from __future__ import annotations

import numpy as np

PRESETS = {                      # warna petunjuk; warna sebenarnya diambil dari tepi gambar
    "white": (255, 255, 255),
    "green": (0, 200, 0),
    "blue": (0, 70, 255),
    "black": (0, 0, 0),
}


def _border(rgb: np.ndarray, k: int = 3) -> np.ndarray:
    """Piksel di pinggiran gambar (k piksel dari tiap sisi) -> (N, 3)."""
    h, w = rgb.shape[:2]
    k = max(1, min(k, h // 4 or 1, w // 4 or 1))
    return np.concatenate([rgb[:k].reshape(-1, 3), rgb[-k:].reshape(-1, 3),
                           rgb[:, :k].reshape(-1, 3), rgb[:, -k:].reshape(-1, 3)])


def border_colors(rgb: np.ndarray, max_n: int = 2) -> list[tuple]:
    """Warna latar paling banyak di tepi gambar (1 warna, atau 2 untuk latar kotak-kotak)."""
    px = _border(rgb).astype(np.int32)
    q = (px // 16)
    keys = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
    vals, counts = np.unique(keys, return_counts=True)
    order = np.argsort(-counts)
    total = len(keys)
    out = []
    for i in order[:max_n]:
        if counts[i] < total * (0.25 if not out else 0.15):     # warna ke-2: kotak-kotak "transparan palsu"
            break
        sel = px[keys == vals[i]]
        out.append(tuple(int(v) for v in np.median(sel, axis=0)))
    return out or [tuple(int(v) for v in np.median(px, axis=0))]


def key_colors(rgb: np.ndarray, mode: str, custom: str = "") -> list[tuple]:
    """Warna yang dihapus untuk mode tertentu. Putih/hijau/biru: warna tepi yang paling mirip petunjuknya
    (layar hijau sungguhan jarang benar-benar 0,255,0)."""
    if mode == "auto":
        return border_colors(rgb)
    if mode == "custom":
        c = (custom or "#00ff00").lstrip("#")
        try:
            return [(int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))]
        except ValueError:
            return [(0, 255, 0)]
    hint = np.array(PRESETS.get(mode, (255, 255, 255)), np.float32)
    px = _border(rgb).astype(np.float32)
    d = np.linalg.norm(px - hint, axis=1)
    near = px[d < 140]
    if len(near) >= max(8, len(px) * 0.05):
        return [tuple(int(v) for v in np.median(near, axis=0))]
    return [tuple(int(v) for v in hint)]


def _dist(rgb: np.ndarray, colors) -> np.ndarray:
    """Jarak warna tiap piksel ke warna kunci terdekat (0..1). Selisih kecerahan ditimbang lebih ringan
    daripada selisih warna, supaya bayangan halus di latar hijau / biru tetap ikut terhapus."""
    f = rgb.astype(np.float32) / 255.0
    best = None
    for c in colors:
        k = np.array(c, np.float32) / 255.0
        diff = f - k
        lum = diff.mean(axis=2, keepdims=True)
        chroma = diff - lum
        d = np.sqrt((chroma ** 2).sum(axis=2) * 1.6 + (lum[..., 0] ** 2) * 1.2)
        best = d if best is None else np.minimum(best, d)
    return best


def remove_background(rgba: np.ndarray, mode: str = "auto", tol: float = 30, soft: float = 20,
                      edge_only: bool = True, custom: str = "", despill: bool = True) -> np.ndarray:
    """Hapus latar -> RGBA baru.
    tol (0..100): seberapa jauh warna masih dianggap latar.
    soft (0..100): kehalusan tepi (peralihan transparan).
    edge_only: hanya latar yang tersambung ke tepi gambar (tulisan putih DI DALAM logo tetap ada)."""
    import cv2
    if mode in ("", "none"):
        return rgba
    rgb = rgba[..., :3]
    a0 = rgba[..., 3].astype(np.float32) / 255.0
    colors = key_colors(rgb, mode, custom)
    d = _dist(rgb, colors)
    t = 0.02 + (max(0.0, min(100.0, tol)) / 100.0) * 0.45
    s = 0.005 + (max(0.0, min(100.0, soft)) / 100.0) * 0.25
    keep = np.clip((d - t) / s, 0.0, 1.0)              # 0 = latar, 1 = isi gambar
    if edge_only:
        cand = (keep < 0.999).astype(np.uint8)          # kandidat latar (termasuk tepi halus)
        n, lab = cv2.connectedComponents(cand, connectivity=4)
        if n > 1:
            edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
            edge = edge[edge != 0]
            touch = np.isin(lab, edge)
            keep = np.where(touch, keep, 1.0)
    alpha = a0 * keep
    out = rgba.copy()
    if despill and mode in ("green", "blue", "custom", "auto"):
        # sisa warna latar yang memantul di tepi objek (pinggiran kehijauan) dinetralkan
        c = np.array(colors[0], np.float32)
        ch = int(np.argmax(c))
        if c[ch] - np.delete(c, ch).max() > 60:          # hanya latar berwarna kuat (hijau / biru / merah)
            f = out[..., :3].astype(np.float32)
            others = np.delete(f, ch, axis=2).max(axis=2)
            edge_px = (alpha > 0) & (keep < 1.0) | (d < t + s * 3)
            f[..., ch] = np.where(edge_px, np.minimum(f[..., ch], others), f[..., ch])
            out[..., :3] = np.clip(f, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(alpha * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return out


def removed_ratio(before: np.ndarray, after: np.ndarray) -> float:
    """Bagian gambar (0..1) yang menjadi transparan."""
    b = before[..., 3] > 8
    return float(((after[..., 3] <= 8) & b).sum()) / max(1, int(b.sum()))
