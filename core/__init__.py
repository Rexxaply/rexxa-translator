"""Inti pipeline Rexxa Translator: deteksi -> OCR -> terjemah -> hapus teks -> typeset."""
import sys


def _ensure_std_streams():
    """Di .exe tanpa konsol (PyInstaller --windowed) sys.stdout & sys.stderr = None.
    Pustaka seperti tqdm, huggingface, loguru (dipakai manga-ocr/EasyOCR saat mengunduh model)
    menulis progres ke sana -> "'NoneType' object has no attribute 'write'".
    Arahkan ke file log di folder data supaya aman (dan bisa dibaca bila ada masalah)."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    import os
    try:
        from .paths import data_dir
        path = data_dir() / "rexxa.log"
        if path.exists() and path.stat().st_size > 5 * 1024 * 1024:   # batasi ukuran log
            path.replace(path.with_suffix(".log.old"))
        stream = open(path, "a", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        stream = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


_ensure_std_streams()
