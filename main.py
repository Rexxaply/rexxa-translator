"""Rexxa Translator — peluncur.

Versi .exe terdiri dari dua bagian:
  RexxaTranslator.exe + _internal/   = MESIN (Python, Qt, OpenCV, PyTorch, OCR). Jarang berubah.
  app/  (core/, gui/, assets/)       = KODE APLIKASI. Diganti oleh update rutin (ukurannya kecil).

File ini adalah satu-satunya kode yang dibekukan ke dalam .exe. Ia mencari folder app/,
memuatnya, dan kalau update kode terakhir rusak, otomatis kembali ke versi sebelumnya (app.old/).

Jalankan dari source:  python main.py
"""
import os
import shutil
import sys
import traceback

# Naikkan HANYA jika daftar pustaka di dalam .exe berubah (paket baru, versi Python/PyTorch baru).
# Update kode yang butuh mesin lebih baru akan otomatis diarahkan ke "update penuh".
ENGINE_VERSION = 1


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _code_dir(base):
    """Di .exe: <folder exe>/app . Dari source: folder ini sendiri."""
    app = os.path.join(base, "app")
    if getattr(sys, "frozen", False) or os.path.isdir(os.path.join(app, "core")):
        return app
    return base


def _show_error(msg):
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, msg, "Rexxa Translator", 0x10)
            return
        except Exception:
            pass
    print(msg, file=sys.stderr)


def _rollback(code):
    """Kembalikan app.old -> app (dipakai kalau update kode membuat aplikasi gagal dibuka)."""
    old = code + ".old"
    if not os.path.isdir(old):
        return False
    broken = code + ".broken"
    shutil.rmtree(broken, ignore_errors=True)
    if os.path.isdir(code):
        os.rename(code, broken)
    os.rename(old, code)
    return True


def _selftest(code):
    """REXXA_SELFTEST=1: muat semua modul aplikasi tanpa membuka jendela, lalu keluar.
    Dipakai GitHub Actions untuk memastikan .exe hasil build benar-benar jalan."""
    import importlib
    import pkgutil
    out = []
    for pkg in ("core", "gui"):
        for m in pkgutil.iter_modules([os.path.join(code, pkg)]):
            importlib.import_module(f"{pkg}.{m.name}")
            out.append(f"{pkg}.{m.name}")
    for opt in ("manga_ocr", "easyocr", "simple_lama_inpainting", "torchvision"):
        try:
            importlib.import_module(opt)
            out.append(opt)
        except ImportError:
            out.append(f"{opt} (TIDAK ADA)")
    # .exe tanpa konsol: pustaka yang menulis progres ke stdout/stderr tidak boleh error
    sys.stderr.write("selftest: stderr OK\n")
    sys.stdout.write("selftest: stdout OK\n")
    out.append("stdout/stderr aman")
    import torch
    import torchvision.ops as ops
    ops.nms(torch.zeros((1, 4)), torch.zeros(1), 0.5)
    out.append("torchvision.ops.nms OK")
    path = os.environ.get("REXXA_SELFTEST_OUT")
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out))


def _ensure_std_streams():
    """.exe tanpa konsol: sys.stdout/stderr = None -> arahkan ke log supaya pustaka yang mencetak
    progres (tqdm, huggingface, loguru) tidak error. Kode aplikasi (core/) juga melakukan ini."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, "RexxaTranslator")
    try:
        os.makedirs(d, exist_ok=True)
        stream = open(os.path.join(d, "rexxa.log"), "a", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        stream = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def main():
    _ensure_std_streams()
    base = _base_dir()
    code = _code_dir(base)
    if getattr(sys, "frozen", False):          # dari source: tidak ada "mesin", update = kode saja
        os.environ["REXXA_ENGINE"] = str(ENGINE_VERSION)
    os.environ["REXXA_BASE"] = base
    sys.path.insert(0, code)
    if os.environ.get("REXXA_SELFTEST"):
        try:
            _selftest(code)
        except Exception:
            path = os.environ.get("REXXA_SELFTEST_OUT")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("GAGAL\n" + traceback.format_exc())
            sys.exit(1)
        sys.exit(0)
    try:
        from gui.main_window import run
    except Exception:
        err = traceback.format_exc()
        if getattr(sys, "frozen", False) and _rollback(code):
            for m in [m for m in sys.modules if m.split(".")[0] in ("core", "gui")]:
                del sys.modules[m]
            try:
                from gui.main_window import run  # noqa: F811
                os.environ["REXXA_ROLLED_BACK"] = "1"
            except Exception:
                _show_error("Rexxa Translator gagal dibuka.\n\n" + traceback.format_exc()[-1500:])
                sys.exit(1)
        else:
            _show_error("Rexxa Translator gagal dibuka.\n\n" + err[-1500:])
            sys.exit(1)
    run()


def _bundle_hint():  # pragma: no cover — TIDAK pernah dipanggil
    """Daftar pustaka untuk PyInstaller. Kode aplikasi dimuat dari luar .exe, jadi PyInstaller
    tidak bisa melihat import-nya; semua yang dipakai app/ harus disebut di sini supaya ikut
    dibundel ke MESIN. Menambah import pihak ketiga baru di app/ = naikkan ENGINE_VERSION."""
    import PySide6.QtCore, PySide6.QtGui, PySide6.QtWidgets, PySide6.QtSvg  # noqa: E401,F401
    import cv2, numpy, PIL.Image, PIL.ImageDraw, PIL.ImageFont, requests, deep_translator  # noqa: E401,F401
    import deep_translator.google  # noqa: F401
    # pustaka standar yang dipakai / mungkin dipakai update kode di masa depan
    import argparse, base64, collections, concurrent.futures, contextlib, copy, csv, ctypes  # noqa: E401,F401
    import dataclasses, datetime, difflib, enum, fnmatch, functools, glob, hashlib, html, io  # noqa: E401,F401
    import itertools, json, logging, math, pathlib, platform, queue, random, re, shutil  # noqa: E401,F401
    import sqlite3, statistics, string, subprocess, tempfile, textwrap, threading, time  # noqa: E401,F401
    import typing, unicodedata, urllib.parse, urllib.request, uuid, webbrowser, zipfile  # noqa: E401,F401
    import xml.etree.ElementTree, email.utils, http.client, gzip, struct, traceback  # noqa: E401,F401


if __name__ == "__main__":
    main()
