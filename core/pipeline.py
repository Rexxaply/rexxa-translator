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
    "translation_cache": True,      # pakai ulang terjemahan teks yang sama (hemat token)
    "font": "",
    "max_font_size": 48,
    "text_presets": None,           # 5 preset teks; None = DEFAULT_PRESETS
    "default_font_size": 0,         # 0 = Auto-Fit (menyesuaikan balon)
    "export_naming": "original",    # original | doc | num  (lihat EXPORT_NAMING)
    "shortcuts": {},                # pintasan keyboard yang diubah pengguna {id: "Ctrl+X"}
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


# Preset 1 = gaya default semua balon (font, tebal, miring, kapital).
DEFAULT_PRESETS = [
    {"font": "", "bold": False, "italic": True, "case": "upper"},    # 1: scanlation (default)
    {"font": "", "bold": True, "italic": True, "case": "upper"},     # 2: teriakan / tebal
    {"font": "", "bold": False, "italic": False, "case": "none"},    # 3: biasa (huruf kecil-besar)
    {"font": "", "bold": False, "italic": False, "case": "upper"},   # 4: kapital tegak (narasi)
    {"font": "", "bold": True, "italic": False, "case": "upper"},    # 5: kapital tegak tebal
]

EXPORT_NAMING = {
    "original": "Nama asli (halaman01.png)",
    "doc": "NamaFolder_001",
    "num": "001",
}


def presets(settings: dict) -> list[dict]:
    p = settings.get("text_presets") or []
    out = []
    for i, d in enumerate(DEFAULT_PRESETS):
        cur = dict(d)
        if i < len(p) and isinstance(p[i], dict):
            cur.update({k: v for k, v in p[i].items() if k in d})
        out.append(cur)
    return out


def sync_default_style(settings: dict):
    """Preset 1 = gaya default: salin ke kunci lama yang dipakai render."""
    p1 = presets(settings)[0]
    settings["font"] = p1["font"]
    settings["italic"] = bool(p1["italic"])
    settings["uppercase"] = p1["case"] == "upper"
    settings["default_bold"] = bool(p1["bold"])


def apply_preset(block, settings: dict, n: int):
    """Terapkan preset ke-n (1..5) ke satu balon."""
    p = presets(settings)[n - 1]
    block.font = p["font"]
    block.bold = bool(p["bold"])
    block.italic = bool(p["italic"])
    block.case = p["case"]
    block.preset = n


def output_name(page, project, settings) -> str:
    ext = settings.get("output_format", "png")
    mode = settings.get("export_naming", "original")
    try:
        idx = project.pages.index(page) + 1
    except ValueError:
        idx = 1
    if mode == "num":
        return f"{idx:03d}.{ext}"
    if mode == "doc":
        return f"{Path(page.path).parent.name or 'Halaman'}_{idx:03d}.{ext}"
    return f"{Path(page.path).stem}.{ext}"


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
    if not s.get("text_presets"):           # 1.7.0: preset teks; preset 1 diisi dari gaya lama
        p = [dict(d) for d in DEFAULT_PRESETS]
        p[0].update(font=s.get("font", ""), italic=bool(s.get("italic", True)),
                    case="upper" if s.get("uppercase", True) else "none")
        s["text_presets"] = p
    sync_default_style(s)
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
        inpaint.auto_style(img, b)
    page.status = "dideteksi"


def step_ocr(page: Page, project: Project, settings: dict, progress=None):
    img = detector.load_image(page.path)
    ocr.ocr_page(img, page.blocks, settings["ocr_engine"], project.source_lang, settings["gpu"], progress)
    page.status = "di-OCR"


def step_translate(page: Page, project: Project, settings: dict, log=None):
    texts = [b.source for b in page.blocks]
    translator.reset_stats()
    res = translator.translate(texts, project.source_lang, project.target_lang,
                               settings["translate_engine"], settings, project.glossary)
    if log:
        s = translator.STATS
        msg = f"[{page.name}] dikirim {s['sent']} teks"
        extra = [f"{s['cached']} dari cache" if s["cached"] else "", f"{s['dupes']} duplikat" if s["dupes"] else "",
                 f"{s['skipped']} tanda baca" if s["skipped"] else ""]
        extra = [e for e in extra if e]
        if extra:
            msg += " · hemat: " + ", ".join(extra)
        if s["tokens_in"] or s["tokens_out"]:
            msg += f" · token masuk {s['tokens_in']} / keluar {s['tokens_out']}"
        log(msg)
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
    sync_default_style(settings)
    final = typeset.render_page(base, page.blocks, project.target_lang, settings.get("font", ""),
                                settings.get("uppercase", True), int(settings.get("max_font_size", 48)),
                                italic=settings.get("italic", True),
                                default_size=int(settings.get("default_font_size", 0) or 0),
                                default_bold=bool(settings.get("default_bold", False)))
    p = output_dir(page, settings) / output_name(page, project, settings)
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
        step_translate(page, project, settings, log)
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
