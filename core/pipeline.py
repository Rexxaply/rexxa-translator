"""Penggabung semua tahap + pengaturan aplikasi."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from . import detector, inpaint, ocr, paths, translator, typeset
from .models import Page, Project

DEFAULT_SETTINGS = {
    "settings_rev": 2,
    "detect_mode": "bubble",        # bubble | easyocr | hybrid
    "ocr_engine": "auto",           # auto | manga-ocr | easyocr
    "translate_engine": "google",   # google | deepl | llm
    "clean_method": "auto",         # auto | fill | opencv | lama
    "gpu": False,
    "deepl_key": "",
    "llm_preset": "Gemini",
    "llm_base_url": translator.LLM_PRESETS["Gemini"][0],
    "llm_model": translator.LLM_PRESETS["Gemini"][1],
    "llm_api_key": "",
    "llm_extra_prompt": "",
    "llm_temperature": 0.3,
    "font": "",
    "max_font_size": 48,
    "uppercase": True,              # gaya scanlation: HURUF KAPITAL
    "italic": True,                 # dan sedikit miring
    "default_stroke": 0,
    "output_format": "png",         # png | jpg | webp
    "output_dir": "",               # kosong = <folder gambar>/translated
    "last_source_lang": "ja",       # bahasa terakhir dipilih di toolbar
    "last_target_lang": "id",
    "update_last_check": "",        # tanggal ISO, cek maks. sekali sehari
    "update_skip_version": "",      # versi yang dipilih "Lewati"
}


def settings_path() -> Path:
    return paths.settings_file()


def load_settings() -> dict:
    paths.migrate_old_data()
    s = dict(DEFAULT_SETTINGS)
    p = settings_path()
    if p.exists():
        try:
            s.update(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    if int(s.get("settings_rev", 0)) < 2:   # 1.5.0: gaya huruf baru ala scanlation sebagai default
        s.update(uppercase=True, italic=True, settings_rev=2)
    return s


def save_settings(s: dict):
    settings_path().write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def output_dir(page: Page, settings: dict) -> Path:
    d = Path(settings.get("output_dir") or (Path(page.path).parent / "translated"))
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- tahap per halaman

def step_detect(page: Page, project: Project, settings: dict):
    img = detector.load_image(page.path)
    page.blocks = detector.detect(img, settings["detect_mode"], project.source_lang, settings["gpu"])
    for b in page.blocks:
        b.stroke_width = int(settings.get("default_stroke", 0))
    page.status = "dideteksi"


def step_ocr(page: Page, project: Project, settings: dict, progress=None):
    img = detector.load_image(page.path)
    ocr.ocr_page(img, page.blocks, settings["ocr_engine"], project.source_lang, settings["gpu"], progress)
    page.status = "di-OCR"


def step_translate(page: Page, project: Project, settings: dict):
    texts = [b.source for b in page.blocks]
    res = translator.translate(texts, project.source_lang, project.target_lang,
                               settings["translate_engine"], settings, project.glossary)
    for b, t in zip(page.blocks, res):
        b.translation = t
    page.status = "diterjemah"


def step_clean(page: Page, settings: dict):
    img = detector.load_image(page.path)
    cleaned = inpaint.clean_page(img, page.blocks, settings["clean_method"])
    out = output_dir(page, settings) / ".cache"
    out.mkdir(exist_ok=True)
    p = out / (Path(page.path).stem + "_clean.png")
    detector.save_image(str(p), cleaned)
    page.cleaned_path = str(p)
    return cleaned


def step_render(page: Page, project: Project, settings: dict, recalc_clean: bool = False):
    if recalc_clean or not page.cleaned_path or not Path(page.cleaned_path).exists():
        base = step_clean(page, settings)
    else:
        base = detector.load_image(page.cleaned_path)
    final = typeset.render_page(base, page.blocks, project.target_lang, settings.get("font", ""),
                                settings.get("uppercase", True), int(settings.get("max_font_size", 48)),
                                italic=settings.get("italic", True))
    ext = settings.get("output_format", "png")
    p = output_dir(page, settings) / f"{Path(page.path).stem}.{ext}"
    detector.save_image(str(p), final)
    page.output_path = str(p)
    page.status = "selesai"
    return final


def process_page(page: Page, project: Project, settings: dict, stages=("detect", "ocr", "translate", "render"),
                 log=print):
    if "detect" in stages:
        log(f"[{page.name}] deteksi balon…")
        step_detect(page, project, settings)
        log(f"[{page.name}] {len(page.blocks)} blok ditemukan")
    if "ocr" in stages and page.blocks:
        log(f"[{page.name}] OCR…")
        step_ocr(page, project, settings)
    if "translate" in stages and page.blocks:
        log(f"[{page.name}] menerjemahkan ({settings['translate_engine']})…")
        step_translate(page, project, settings)
    if "render" in stages:
        log(f"[{page.name}] hapus teks & typeset…")
        step_render(page, project, settings, recalc_clean=True)
        log(f"[{page.name}] selesai -> {page.output_path}")


def export_zip(project: Project, zip_path: str):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in project.pages:
            if p.output_path and Path(p.output_path).exists():
                z.write(p.output_path, Path(p.output_path).name)


def export_text(project: Project, txt_path: str):
    """Skrip terjemahan (format umum scanlation) untuk proofreader."""
    lines = []
    for p in project.pages:
        lines.append(f"=== {p.name} ===")
        for i, b in enumerate(p.blocks, 1):
            lines.append(f"{i}. {b.source}\n   -> {b.translation}")
        lines.append("")
    Path(txt_path).write_text("\n".join(lines), encoding="utf-8")
