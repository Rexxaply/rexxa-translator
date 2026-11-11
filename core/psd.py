"""Penulis file Photoshop (.psd) sederhana — tanpa pustaka tambahan.

Mendukung: RGB 8-bit, beberapa lapisan RGBA (posisi, nama Unicode, sembunyi/tampil, opacity),
gambar gabungan (composite) untuk pratinjau. Kanal dikompres RLE (PackBits) seperti Photoshop.
Bisa dibuka Photoshop, Photopea, GIMP, Krita, Clip Studio, dll.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

import numpy as np


@dataclass
class Layer:
    name: str
    rgba: np.ndarray          # H x W x 4 uint8 (RGBA)
    left: int = 0
    top: int = 0
    visible: bool = True
    opacity: int = 255


def _packbits_row(row: bytes) -> bytes:
    """PackBits satu baris. Hanya deret >= 3 byte sama yang diringkas; sisanya disalin per 128 byte
    (cepat walau gambar penuh raster/screentone)."""
    n = len(row)
    if n == 0:
        return b""
    a = np.frombuffer(row, dtype=np.uint8)
    # awal setiap deret nilai yang sama
    change = np.flatnonzero(np.diff(a)) + 1
    starts = np.concatenate(([0], change))
    lens = np.diff(np.concatenate((starts, [n])))
    out = bytearray()
    lit_start = 0

    def flush_literal(s, e):
        while s < e:
            k = min(128, e - s)
            out.append(k - 1)
            out.extend(row[s:s + k])
            s += k

    for st, ln in zip(starts[lens >= 3].tolist(), lens[lens >= 3].tolist()):
        flush_literal(lit_start, st)
        v = row[st]
        while ln >= 3:
            k = min(128, ln)
            out.append((257 - k) & 0xFF)        # -(k-1)
            out.append(v)
            ln -= k
            st += k
        lit_start = st                           # sisa 1-2 byte ikut literal berikutnya
    flush_literal(lit_start, n)
    return bytes(out)


def _rle_channel(ch: np.ndarray) -> tuple[bytes, bytes]:
    """(tabel panjang tiap baris, data) untuk satu kanal H x W."""
    rows = [_packbits_row(ch[y].tobytes()) for y in range(ch.shape[0])]
    counts = struct.pack(f">{len(rows)}H", *[len(r) for r in rows]) if rows else b""
    return counts, b"".join(rows)


def _pascal(name: str) -> bytes:
    b = name.encode("latin-1", "replace")[:255]
    s = bytes([len(b)]) + b
    return s + b"\0" * ((4 - len(s) % 4) % 4)


def _luni(name: str) -> bytes:
    u = name.encode("utf-16-be")
    data = struct.pack(">I", len(name)) + u
    if len(data) % 2:
        data += b"\0"
    if len(data) % 4:
        data += b"\0" * (4 - len(data) % 4)
    return b"8BIMluni" + struct.pack(">I", len(data)) + data


def write_psd(path: str, width: int, height: int, layers: list[Layer], composite: np.ndarray):
    """layers: urutan dari BAWAH ke ATAS. composite: H x W x 3 RGB uint8."""
    recs, chan_data = [], []
    for L in layers:
        h, w = L.rgba.shape[:2]
        top, left = int(L.top), int(L.left)
        chans = []
        for cid, idx in ((-1, 3), (0, 0), (1, 1), (2, 2)):
            counts, data = _rle_channel(np.ascontiguousarray(L.rgba[..., idx]))
            blob = struct.pack(">H", 1) + counts + data
            chans.append((cid, blob))
        rec = struct.pack(">4i", top, left, top + h, left + w)
        rec += struct.pack(">H", len(chans))
        for cid, blob in chans:
            rec += struct.pack(">hI", cid, len(blob))
        flags = 0 if L.visible else 2
        rec += b"8BIMnorm" + struct.pack(">BBBB", max(0, min(255, int(L.opacity))), 0, flags, 0)
        extra = struct.pack(">I", 0) + struct.pack(">I", 0) + _pascal(L.name) + _luni(L.name)
        rec += struct.pack(">I", len(extra)) + extra
        recs.append(rec)
        chan_data.append(b"".join(blob for _, blob in chans))

    layer_info = struct.pack(">h", len(layers)) + b"".join(recs) + b"".join(chan_data)
    if len(layer_info) % 2:
        layer_info += b"\0"
    lmi = struct.pack(">I", len(layer_info)) + layer_info + struct.pack(">I", 0)

    with open(path, "wb") as f:
        f.write(b"8BPS" + struct.pack(">H", 1) + b"\0" * 6)
        f.write(struct.pack(">HIIHH", 3, height, width, 8, 3))      # 3 kanal, RGB 8-bit
        f.write(struct.pack(">I", 0))                                # color mode data
        f.write(struct.pack(">I", 0))                                # image resources
        f.write(struct.pack(">I", len(lmi)) + lmi)
        # gambar gabungan: RLE, semua tabel baris dulu lalu data per kanal
        counts_all, data_all = [], []
        for c in range(3):
            counts, data = _rle_channel(np.ascontiguousarray(composite[..., c]))
            counts_all.append(counts)
            data_all.append(data)
        f.write(struct.pack(">H", 1) + b"".join(counts_all) + b"".join(data_all))


def bgr_to_rgba(img_bgr: np.ndarray) -> np.ndarray:
    rgb = img_bgr[..., 2::-1] if img_bgr.ndim == 3 else np.repeat(img_bgr[..., None], 3, axis=2)
    a = np.full(rgb.shape[:2] + (1,), 255, np.uint8)
    return np.ascontiguousarray(np.concatenate([rgb, a], axis=2))


def page_psd(path: str, original_bgr: np.ndarray, clean_bgr: np.ndarray, final_bgr: np.ndarray,
             text_layers: list, show_raw: bool = False):
    """PSD satu halaman: Raw (asli) · Bersih · satu lapisan per balon teks.
    text_layers: [(nama, PIL RGBA, x, y)]."""
    H, W = final_bgr.shape[:2]
    layers = []
    if original_bgr is not None and original_bgr.shape[:2] == (H, W):
        layers.append(Layer("Raw (asli)", bgr_to_rgba(original_bgr), visible=show_raw))
    layers.append(Layer("Bersih (tanpa teks)", bgr_to_rgba(clean_bgr)))
    for name, im, x, y in text_layers:
        arr = np.asarray(im.convert("RGBA"))
        # potong ke batas kanvas & buang tepi kosong (file lebih kecil)
        x0, y0 = max(0, -x), max(0, -y)
        x1, y1 = min(arr.shape[1], W - x), min(arr.shape[0], H - y)
        if x1 <= x0 or y1 <= y0:
            continue
        arr = arr[y0:y1, x0:x1]
        ys, xs = np.nonzero(arr[..., 3])
        if not len(ys):
            continue
        arr = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        layers.append(Layer(name, np.ascontiguousarray(arr), left=x + x0 + int(xs.min()), top=y + y0 + int(ys.min())))
    write_psd(path, W, H, layers, np.ascontiguousarray(final_bgr[..., 2::-1]))
