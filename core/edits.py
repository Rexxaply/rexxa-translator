"""Suntingan gambar manual di atas hasil hapus-teks (disimpan di proyek, bisa di-undo).

Jenis (dict di Page.edits):
  {"op": "heal",    "pts": [[x, y], ...], "r": 12}            Healing brush: goresan kuas -> latar dibuat ulang AI
  {"op": "erase",   "poly": [[x, y], ...]}                    Hapus area (pen / bentuk) -> dibuat ulang AI (LaMa)
  {"op": "fill",    "poly": [[x, y], ...], "color": "#FFF"}   Isi area dengan warna
  {"op": "restore", "poly": [[x, y], ...]}                    Kembalikan piksel gambar asli di area
Semua koordinat dalam piksel gambar asli.
"""
from __future__ import annotations

import json

import cv2
import numpy as np


def _hex_bgr(c: str):
    c = (c or "#FFFFFF").lstrip("#")
    try:
        return int(c[4:6], 16), int(c[2:4], 16), int(c[0:2], 16)
    except ValueError:
        return 255, 255, 255


def edit_mask(shape, e: dict) -> np.ndarray:
    H, W = shape[:2]
    m = np.zeros((H, W), np.uint8)
    if e.get("op") == "heal":
        pts = np.array(e.get("pts") or [], np.int32).reshape(-1, 2)
        r = max(1, int(e.get("r", 10)))
        if len(pts) == 1:
            cv2.circle(m, tuple(int(v) for v in pts[0]), r, 255, -1)
        elif len(pts) > 1:
            cv2.polylines(m, [pts], False, 255, thickness=2 * r, lineType=cv2.LINE_AA)
            for p in pts[[0, -1]]:
                cv2.circle(m, tuple(int(v) for v in p), r, 255, -1)
    else:
        poly = np.array(e.get("poly") or [], np.int32).reshape(-1, 2)
        if len(poly) >= 3:
            cv2.fillPoly(m, [poly], 255, lineType=cv2.LINE_AA)
    return (m > 0).astype(np.uint8) * 255


def _ai_fill(img: np.ndarray, mask: np.ndarray, method: str) -> np.ndarray:
    from . import inpaint
    # sedikit diperlebar supaya tepi objek / bayangan tipis ikut hilang
    m = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    if method in ("auto", "lama") and inpaint.lama_available():
        return inpaint._inpaint_lama(img, m)
    return inpaint._inpaint_opencv(img, m)


def apply_one(img: np.ndarray, e: dict, original: np.ndarray | None = None, method: str = "auto") -> np.ndarray:
    m = edit_mask(img.shape, e)
    if not m.any():
        return img
    op = e.get("op")
    if op in ("heal", "erase"):
        return _ai_fill(img, m, method)
    out = img.copy()
    if op == "fill":
        col = np.array(_hex_bgr(e.get("color")), np.uint8)
        a = cv2.GaussianBlur(m, (3, 3), 0).astype(np.float32)[..., None] / 255.0
        out = (out * (1 - a) + col * a).astype(np.uint8)
    elif op == "restore" and original is not None and original.shape == img.shape:
        out[m > 0] = original[m > 0]
    return out


def key(e: dict) -> str:
    return json.dumps(e, sort_keys=True)


def apply_all(page, base: np.ndarray, original: np.ndarray | None, method: str = "auto",
              base_key: str = "") -> np.ndarray:
    """Terapkan semua suntingan halaman. Hasil disimpan di memori: bila suntingan baru hanya
    ditambahkan di akhir, hanya suntingan baru yang dikerjakan (cepat untuk healing brush)."""
    edits = list(getattr(page, "edits", None) or [])
    if not edits:
        return base
    keys = [key(e) for e in edits]
    cache = getattr(page, "_edit_cache", None)
    start, img = 0, base
    if cache and cache.get("base") == base_key and keys[:len(cache["keys"])] == cache["keys"]:
        start, img = len(cache["keys"]), cache["img"]
    for e in edits[start:]:
        img = apply_one(img, e, original, method)
    page._edit_cache = {"base": base_key, "keys": keys, "img": img}
    return img
