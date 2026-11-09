"""OCR per blok teks.

- "manga-ocr" : khusus Jepang (vertikal/horizontal, furigana) — paling akurat untuk manga.
- "easyocr"   : Korea, Mandarin, Inggris, dan bahasa lain.
- "auto"      : manga-ocr untuk ja, easyocr untuk sisanya.
"""
from __future__ import annotations

import re

import cv2
import numpy as np
from PIL import Image

from .models import TextBlock

_manga_ocr = None


def _get_manga_ocr():
    global _manga_ocr
    if _manga_ocr is None:
        from manga_ocr import MangaOcr
        _manga_ocr = MangaOcr()
    return _manga_ocr


def _crop(img: np.ndarray, b: TextBlock, pad: int = 4) -> np.ndarray:
    h, w = img.shape[:2]
    x0, y0 = max(0, b.x - pad), max(0, b.y - pad)
    x1, y1 = min(w, b.x + b.w + pad), min(h, b.y + b.h + pad)
    return img[y0:y1, x0:x1]


def ocr_block(img: np.ndarray, b: TextBlock, engine: str, lang: str, gpu: bool = False) -> str:
    crop = _crop(img, b)
    if crop.size == 0:
        return ""
    if engine == "auto":
        engine = "manga-ocr" if lang == "ja" else "easyocr"

    if engine == "manga-ocr":
        mocr = _get_manga_ocr()
        pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        text = mocr(pil)
    elif engine == "easyocr":
        from .detector import get_easyocr
        reader = get_easyocr(lang, gpu)
        # paragraph=True menggabungkan baris; urut atas->bawah
        res = reader.readtext(crop, detail=0, paragraph=True)
        text = " ".join(res)
    else:
        raise ValueError(f"Engine OCR tidak dikenal: {engine}")
    return clean_text(text, lang)


def clean_text(text: str, lang: str) -> str:
    text = text.strip()
    if lang in ("ja", "zh", "zh-tw"):
        text = text.replace(" ", "")
        text = re.sub(r"[.．]{2,}|…+", "…", text)
    else:
        text = re.sub(r"\s+", " ", text)
    return text


def ocr_page(img: np.ndarray, blocks: list[TextBlock], engine: str, lang: str, gpu: bool = False,
             progress=None):
    errors = []
    for i, b in enumerate(blocks):
        try:
            b.source = ocr_block(img, b, engine, lang, gpu)
        except ImportError:
            raise
        except Exception as e:  # satu blok gagal jangan hentikan halaman
            b.source = ""          # jangan sampai pesan error ikut diterjemahkan/ditempel
            errors.append(str(e))
        if progress:
            progress(i + 1, len(blocks))
    if blocks and len(errors) == len(blocks):
        raise RuntimeError(ocr_error_hint(errors[0]))
    check_language(blocks, lang)
    return blocks


LANG_LABEL = {"ja": "Japanese", "ko": "Korean", "zh": "Chinese", "zh-tw": "Chinese (Traditional)"}


def check_language(blocks, lang):
    """Bahasa asal diset JP/KR/CN tapi hampir semua yang terbaca huruf Latin
    -> hampir pasti salah pilih bahasa (mis. komik bahasa Inggris)."""
    if lang not in LANG_LABEL:
        return
    text = "".join(b.source for b in blocks)
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 8:
        return
    latin = sum(1 for c in letters if c.isascii() or "\uff21" <= c <= "\uff5a")  # termasuk huruf Latin lebar
    if latin / len(letters) > 0.6:
        for b in blocks:
            b.source = ""
        raise RuntimeError(
            f"Teks di halaman ini sepertinya huruf Latin (mis. bahasa Inggris), "
            f"tapi bahasa asal diset ke {LANG_LABEL[lang]}.\n\n"
            f"Ganti pilihan bahasa asal di toolbar (mis. ke EN English), lalu klik ⚡ Terjemahkan lagi.")


def ocr_error_hint(msg: str) -> str:
    if "torchvision::nms" in msg or "torchvision" in msg and "operator" in msg:
        return ("OCR gagal: versi torch dan torchvision tidak cocok, atau torchvision tidak ikut "
                "terbundel ke .exe.\n\nPerbaikan: jalankan fix_torch.bat, lalu build_exe.bat lagi.\n\n"
                f"Detail: {msg}")
    return f"OCR gagal untuk semua blok: {msg}"
