"""Hemat sumber daya saat menerjemahkan banyak halaman (supaya PC spesifikasi rendah tidak
kehabisan memori / force close, dan aplikasi tetap responsif).

- Mode "hemat" dipilih otomatis bila RAM < 8 GB atau CPU <= 4 inti (bisa dipaksa di Pengaturan).
- Jumlah thread OpenCV / PyTorch dibatasi supaya 1 inti tetap bebas untuk tampilan aplikasi.
- Setelah setiap halaman: cache gambar per halaman dilepas & memori dibersihkan.
- AI hapus teks (LaMa) memproses potongan yang lebih kecil di mode hemat.
"""
from __future__ import annotations

import gc
import os

_low = None


def total_ram_gb() -> float:
    try:
        if os.name == "nt":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys / 1024 ** 3
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3
    except Exception:
        return 16.0


def free_ram_gb() -> float:
    try:
        if os.name == "nt":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullAvailPhys / 1024 ** 3
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_AVPHYS_PAGES") / 1024 ** 3
    except Exception:
        return 8.0


def low_end(settings: dict | None = None) -> bool:
    mode = (settings or {}).get("perf_mode", "auto")
    if mode == "hemat":
        return True
    if mode == "normal":
        return False
    global _low
    if _low is None:
        _low = total_ram_gb() < 7.5 or (os.cpu_count() or 4) <= 4
    return _low


def describe(settings: dict | None = None) -> str:
    return (f"RAM {total_ram_gb():.1f} GB, {os.cpu_count() or '?'} inti CPU -> mode "
            + ("hemat" if low_end(settings) else "normal"))


def apply(settings: dict | None = None):
    """Batasi thread supaya aplikasi tetap responsif (dipanggil sebelum proses besar)."""
    n = os.cpu_count() or 2
    use = max(1, n - 1) if not low_end(settings) else max(1, min(n - 1, 2))
    try:
        import cv2
        cv2.setNumThreads(use)
    except Exception:
        pass
    try:
        import sys
        if "torch" in sys.modules:
            import torch
            torch.set_num_threads(use)
    except Exception:
        pass
    from . import inpaint
    inpaint.LAMA_MAX_SIDE = 640 if low_end(settings) else 1024


def release(page=None, keep_current: bool = False):
    """Lepaskan memori setelah satu halaman selesai."""
    if page is not None and not keep_current:
        for attr in ("_edit_cache",):
            if hasattr(page, attr):
                try:
                    delattr(page, attr)
                except Exception:
                    pass
    gc.collect()
    try:
        import sys
        if "torch" in sys.modules:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    except Exception:
        pass
