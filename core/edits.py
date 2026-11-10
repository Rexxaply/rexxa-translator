"""Suntingan gambar manual di atas hasil hapus-teks (disimpan di proyek, bisa di-undo).

Jenis (dict di Page.edits):
  {"op": "heal",    "pts": [[x, y], ...], "r": 12}            Healing brush: goresan kuas -> latar dibuat ulang AI
  {"op": "erase",   "poly": [[x, y], ...]}                    Hapus area (pen / bentuk) -> dibuat ulang AI (LaMa)
  {"op": "fill",    "poly": [[x, y], ...], "color": "#FFF"}   Isi area dengan warna
  {"op": "restore", "poly": [[x, y], ...]}                    Kembalikan piksel gambar asli di area
  {"op": "stroke",  "pts": [[x, y], ...], "w": 3, "color": "#000"}   Alat garis: gambar garis bebas / lurus
  {"op": "outline", "poly": [[x, y], ...], "w": 3, "color": "#000", "fill": "#FFF"|""}
                                                              Garis tepi tertutup (mis. menggambar ulang balon),
                                                              opsional diisi warna di dalamnya
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


def _smooth(pts: np.ndarray, closed: bool, it: int = 2) -> np.ndarray:
    """Haluskan goresan tangan (Chaikin) supaya garis tidak bergerigi."""
    if len(pts) < 3:
        return pts
    for _ in range(it):
        p = np.vstack([pts, pts[:1]]) if closed else pts
        q = 0.75 * p[:-1] + 0.25 * p[1:]
        r = 0.25 * p[:-1] + 0.75 * p[1:]
        mid = np.empty((len(q) * 2, 2), np.float32)
        mid[0::2], mid[1::2] = q, r
        pts = mid if closed else np.vstack([p[:1], mid, p[-1:]])
    return pts


def _draw_lines(img: np.ndarray, e: dict, closed: bool) -> np.ndarray:
    key_ = "poly" if closed else "pts"
    pts = np.array(e.get(key_) or [], np.float32).reshape(-1, 2)
    if not len(pts):
        return img
    w = max(1, int(e.get("w", 3)))
    col = tuple(int(v) for v in _hex_bgr(e.get("color") or "#000000"))
    out = img.copy()
    if closed and len(pts) >= 3 and e.get("fill"):
        fm = np.zeros(img.shape[:2], np.uint8)
        cv2.fillPoly(fm, [np.round(pts).astype(np.int32)], 255, lineType=cv2.LINE_AA)
        a = fm.astype(np.float32)[..., None] / 255.0
        fc = np.array(_hex_bgr(e["fill"]), np.float32)
        out = (out * (1 - a) + fc * a).astype(np.uint8)
    # sudut tajam bentuk (kotak) dipertahankan; goresan tangan / oval dihaluskan
    if not (closed and len(pts) <= 6):
        pts = _smooth(pts, closed)
    SH = 4                                      # koordinat sub-piksel (garis lebih halus)
    ip = np.round(pts * (1 << SH)).astype(np.int32)
    if len(ip) == 1:
        cv2.circle(out, tuple(int(v) for v in ip[0]), (w * (1 << SH)) // 2, col, -1, cv2.LINE_AA, SH)
    else:
        cv2.polylines(out, [ip], closed, col, w, cv2.LINE_AA, SH)
        if not closed and w > 2:                # ujung garis membulat
            for p in ip[[0, -1]]:
                cv2.circle(out, tuple(int(v) for v in p), (w * (1 << SH)) // 2, col, -1, cv2.LINE_AA, SH)
    return out


def apply_one(img: np.ndarray, e: dict, original: np.ndarray | None = None, method: str = "auto") -> np.ndarray:
    if e.get("op") == "stroke":
        return _draw_lines(img, e, closed=False)
    if e.get("op") == "outline":
        return _draw_lines(img, e, closed=True)
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
