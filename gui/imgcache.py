"""Cache gambar untuk tampilan (thread-safe).

Setelah render, gambar hasil yang masih ada di memori langsung diserahkan ke tampilan, jadi
tampilan tidak perlu membaca & men-decode ulang file PNG dari disk (yang tadinya terjadi 2-3 kali
setiap render: gambar asli, hasil, dan thumbnail). Kunci = path + waktu ubah + ukuran file, jadi
file yang berubah selalu dibaca ulang."""
from __future__ import annotations

import os
import threading
from collections import OrderedDict

from PySide6.QtGui import QImage

_LOCK = threading.Lock()
_CACHE: "OrderedDict[str, tuple]" = OrderedDict()
MAX_MB = 160            # diperkecil di mode hemat


def _key(path: str):
    try:
        st = os.stat(path)
        return st.st_mtime_ns, st.st_size
    except OSError:
        return None


def key(path: str):
    return _key(path)


def _trim():
    tot = sum(v[1].sizeInBytes() for v in _CACHE.values())
    while _CACHE and (tot > MAX_MB * 1024 * 1024 or len(_CACHE) > 8):
        _, (_k, im) = _CACHE.popitem(last=False)
        tot -= im.sizeInBytes()


def put_np(path: str, img) -> None:
    """Simpan gambar BGR (numpy) yang BARU SAJA ditulis ke path (dipanggil dari thread proses)."""
    try:
        k = _key(path)
        if k is None or img is None or img.ndim != 3:
            return
        h, w = img.shape[:2]
        import numpy as np
        arr = np.ascontiguousarray(img)
        qi = QImage(arr.data, w, h, arr.strides[0], QImage.Format.Format_BGR888).copy()
        with _LOCK:
            _CACHE.pop(path, None)
            _CACHE[path] = (k, qi)
            _trim()
    except Exception:
        pass


def get(path: str) -> QImage:
    k = _key(path)
    with _LOCK:
        hit = _CACHE.get(path)
        if hit is not None and hit[0] == k:
            _CACHE.move_to_end(path)
            return hit[1]
    qi = QImage(path)
    if k is not None and not qi.isNull():
        with _LOCK:
            _CACHE[path] = (k, qi)
            _trim()
    return qi


def thumb(path: str, height: int = 128) -> QImage | None:
    """Thumbnail dari gambar yang sudah ada di cache (None bila belum ada)."""
    k = _key(path)
    with _LOCK:
        hit = _CACHE.get(path)
    if hit is None or hit[0] != k:
        return None
    from PySide6.QtCore import Qt
    return hit[1].scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)


def clear():
    with _LOCK:
        _CACHE.clear()
