"""Penggabung semua tahap + pengaturan aplikasi."""
from __future__ import annotations

import json
import zipfile

import numpy as np
from pathlib import Path

from . import detector, inpaint, ocr, paths, translator, typeset
from .models import Page, Project, TextBlock

DEFAULT_SETTINGS = {
    "settings_rev": 2,
    "detect_mode": "bubble",        # bubble | easyocr | hybrid
    "ocr_engine": "auto",           # auto | manga-ocr | easyocr
    "translate_engine": "google",   # google | deepl | llm
    "clean_method": "auto",         # auto | fill | opencv | lama
    "auto_patch": True,             # setelah hapus teks: area yang kurang mulus ditambal area serupa
    "auto_lines": True,             # setelah hapus teks: garis balon yang terputus disambung ulang
    "gpu": False,
    "deepl_key": "",
    "llm_preset": "Gemini",
    "llm_base_url": translator.LLM_PRESETS["Gemini"][0],
    "llm_model": translator.LLM_PRESETS["Gemini"][1],
    "llm_api_key": "",
    "llm_extra_prompt": "",
    "llm_temperature": 0.3,
    "tl_style": "alami",            # gaya bahasa (core/skills.py STYLES)
    "tl_honorific": "keep",         # keep | translate
    "story_memory": True,           # pakai memori cerita (tokoh, panggilan) saat menerjemahkan
    "story_context": True,          # sertakan akhir halaman sebelumnya sebagai konteks (LLM)
    "credits": None,                # halaman kredit & watermark (core/skills.py DEFAULT_CREDITS)
    "translation_cache": True,      # pakai ulang terjemahan teks yang sama (hemat token)
    "font": "",
    "max_font_size": 64,
    "text_presets": None,           # 5 preset teks; None = DEFAULT_PRESETS
    "default_font_size": 0,         # 0 = Auto-Fit (menyesuaikan balon)
    "line_spacing": 1.2,            # jarak baris default (1.0 = rapat; manga umumnya 1.15–1.25)
    "sfx_font_match": True,         # teks spesial: cocokkan font otomatis
    "auto_title": True,             # ganti logo judul otomatis bila judul seri diisi
    "font_match_system": True,      # boleh memakai font perangkat (Windows/Fonts)
    "font_match_online": True,      # cadangan: cari di Google Fonts bila font lokal kurang mirip
    "font_match_all": True,         # cocokkan font untuk semua teks (diingat per proyek)
    "perf_mode": "auto",            # auto | hemat | normal  (hemat = ramah PC spesifikasi rendah)
    "export_naming": "original",    # original | doc | num  (lihat EXPORT_NAMING)
    "shortcuts": {},                # pintasan keyboard yang diubah pengguna {id: "Ctrl+X"}
    "uppercase": True,              # gaya scanlation: HURUF KAPITAL
    "italic": True,                 # dan sedikit miring
    "default_stroke": 0,
    "line_width": 3,                # alat garis: tebal (px)
    "line_color": "#000000",        # alat garis: warna
    "recent_projects": [],
    "recent_opened": {},            # {path proyek: waktu terakhir dibuka}          # proyek terakhir (layar awal), terbaru dulu
    "box_mode": "box",              # kotak manual baru: box (kotak saja) | ocr (+ baca teks) | ocr_tr (+ terjemah)
    "output_format": "png",         # png | jpg | webp
    "output_dir": "",               # kosong = folder kerja tersembunyi (data aplikasi)
    "work_keep_days": 30,           # folder kerja yang tidak dibuka sekian hari dihapus otomatis (0 = jangan)
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
    ensure_engine_presets(s)
    return s


# ---------------------------------------------------------------- preset engine terjemahan
# Satu preset = engine + kunci/alamat/model yang dipakai. Beberapa preset bisa disimpan (mis. "Gemini" dan
# "OpenRouter"); kalau satu sedang gangguan tinggal pindah preset. Nilai preset aktif juga ditulis ke kunci
# biasa (translate_engine, llm_model, …) supaya bagian lain aplikasi tidak perlu berubah.
ENGINE_KEYS = ("translate_engine", "deepl_key", "llm_preset", "llm_base_url", "llm_model", "llm_api_key",
               "llm_temperature")


def engine_values(s: dict) -> dict:
    return {k: s.get(k, DEFAULT_SETTINGS.get(k)) for k in ENGINE_KEYS}


def ensure_engine_presets(s: dict):
    """Pastikan ada daftar preset; pertama kali dibuat satu preset "Default" dari pengaturan sekarang."""
    lst = [p for p in (s.get("engine_presets") or []) if isinstance(p, dict) and str(p.get("name", "")).strip()]
    if not lst:
        lst = [dict(engine_values(s), name="Default")]
    s["engine_presets"] = lst
    if s.get("engine_preset") not in [p["name"] for p in lst]:
        s["engine_preset"] = lst[0]["name"]
    return lst


def find_engine_preset(s: dict, name: str):
    for p in s.get("engine_presets") or []:
        if p.get("name") == name:
            return p
    return None


def apply_engine_preset(s: dict, name: str) -> bool:
    """Jadikan preset `name` aktif: nilainya disalin ke pengaturan yang dipakai saat menerjemahkan."""
    p = find_engine_preset(s, name)
    if p is None:
        return False
    for k in ENGINE_KEYS:
        if k in p:
            s[k] = p[k]
    s["engine_preset"] = name
    return True


def store_engine_preset(s: dict, name: str | None = None):
    """Simpan nilai engine yang sedang berlaku ke preset (bawaan: preset aktif)."""
    name = name or s.get("engine_preset") or "Default"
    p = find_engine_preset(s, name)
    if p is None:
        p = {"name": name}
        s.setdefault("engine_presets", []).append(p)
    p.update(engine_values(s))
    return p


def save_settings(s: dict):
    settings_path().write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def output_dir(page: Page, settings: dict) -> Path:
    from .paths import work_dir
    return work_dir(page.path, settings.get("output_dir") or "")


# ---------------------------------------------------------------- tahap per halaman

def step_detect(page: Page, project: Project, settings: dict):
    img = detector.load_image(page.path)
    page.blocks = detector.detect(img, settings["detect_mode"], project.source_lang, settings["gpu"])
    page._clean_sigs = None           # balon baru semua -> hapus teks penuh
    for b in page.blocks:
        b.stroke_width = int(settings.get("default_stroke", 0))
        inpaint.auto_style(img, b)
    if settings.get("sfx_font_match", True):
        match_sfx_fonts(img, page.blocks, settings)
    # halaman judul (logo seri): hanya di beberapa halaman awal & bila judul seri sudah diisi
    if project.series_title and settings.get("auto_title", True):
        try:
            idx = project.pages.index(page)
        except ValueError:
            idx = 0
        if idx < 3:
            add_title_block(img, page, project, settings, strict=True)
    page.status = "dideteksi"


def add_title_block(img, page: Page, project: Project, settings: dict, strict: bool = False):
    """Cari logo judul di halaman lalu jadikan blok "title". strict: hanya halaman yang jelas
    halaman judul (latar polos gelap/terang di sekeliling logo). Mengembalikan blok atau None."""
    import cv2
    import numpy as np
    from . import titlelogo
    rect, mask = titlelogo.find_title(img)
    if rect is None:
        return None
    x, y, w, h = rect
    if strict:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        H, W = gray.shape
        e = int(h * 0.5)
        ring = np.ones((H, W), bool)
        ring[max(0, y):y + h, max(0, x):x + w] = False
        win = np.zeros((H, W), bool)
        win[max(0, y - e):y + h + e, max(0, x - e):x + w + e] = True
        vals = gray[ring & win]
        if vals.size == 0 or np.std(vals) > 28:        # di sekitar logo ada gambar -> bukan halaman judul
            return None
    # teks lain yang tertumpuk di logo (hasil deteksi biasa) dibuang
    def inside(b):
        cx, cy = b.x + b.w / 2, b.y + b.h / 2
        return x <= cx <= x + w and y <= cy <= y + h
    page.blocks = [b for b in page.blocks if b.kind == "title" or not inside(b)]
    page.blocks = [b for b in page.blocks if b.kind != "title"]
    b = TextBlock(x=x, y=y, w=w, h=h, kind="title", translation=project.series_title,
                  source="[logo judul]", text_rect=[x, y, w, h])
    try:
        from . import fontmatch
        f = fontmatch.best_font(img, rect, int(h * 0.15), heavy=True,
                                include_system=bool(settings.get("font_match_system", True)),
                                online=bool(settings.get("font_match_online", True)))
        if f:
            b.font = f
    except Exception:
        pass
    page.blocks.insert(0, b)
    return b


FONT_CAT_LABEL = {"dialog": "Dialog", "dialog-italic": "Dialog miring (bisikan / pikiran)",
                  "dialog-bold": "Dialog tebal (teriakan)", "narration": "Narasi / teks bebas",
                  "narration-lower": "Narasi huruf kecil (gumaman)"}
FONT_OK = 3.5          # skor kemiripan maksimum supaya font hasil pencocokan dipakai


def font_category(b, feat, page_stroke: float) -> str:
    """Golongan gaya teks asli: dialog / dialog-italic / dialog-bold / narration / narration-lower."""
    letters = [c for c in (b.source or "") if c.isalpha()]
    lower = bool(letters) and sum(c.islower() for c in letters) > 0.5 * len(letters)
    if b.kind == "free":
        return "narration-lower" if lower else "narration"
    if feat is not None and abs(feat.get("slant", 0)) > 0.15:
        return "dialog-italic"
    if feat is not None and page_stroke and feat.get("stroke", 0) > page_stroke * 1.4:
        return "dialog-bold"
    return "dialog"


def auto_fonts(img, page: Page, project: Project, settings: dict, log=None, only=None):
    """Pilih font yang mirip dengan teks asli untuk SEMUA teks (bukan hanya SFX), per golongan gaya.
    Font yang terpilih DIINGAT di proyek (project.font_memory), jadi halaman berikutnya langsung
    memakai font yang sama: cepat dan konsisten se-chapter. Kotak yang fontnya dipilih manual
    tidak diubah."""
    if not settings.get("font_match_all", True):
        return
    from . import fontmatch
    from . import fontmatch as _fm0
    for b in (page.blocks if only is None else only):
        # font hiasan yang dulu dipilih OTOMATIS (bukan pilihan manual) dilepas, lalu dicocokkan ulang
        if b.font and b.font_cat and not getattr(b, "sfx", False) and _fm0.is_decorative(b.font):
            b.font = ""
    blocks = [b for b in (page.blocks if only is None else only)
              if b.kind in ("bubble", "free") and not getattr(b, "sfx", False) and not b.font
              and b.text_rect and len(b.text_rect) == 4]
    if not blocks:
        return
    feats = {}
    for b in blocks:
        try:
            feats[b.id] = fontmatch.source_features(img, b.text_rect, b.src_h)
        except Exception:
            feats[b.id] = None
    strokes = [f["stroke"] for f in feats.values() if f]
    page_stroke = float(np.median(strokes)) if strokes else 0.0
    mem = project.font_memory
    from . import fontmatch as _fm
    for cat in list(mem):                   # font hiasan yang dulu terpilih otomatis: cari ulang
        if mem[cat] and _fm.is_decorative(mem[cat]):
            del mem[cat]
    by_cat = {}
    for b in blocks:
        b.font_cat = font_category(b, feats.get(b.id), page_stroke)
        by_cat.setdefault(b.font_cat, []).append(b)
    for cat, bs in by_cat.items():
        if cat not in mem or (mem[cat] and not Path(mem[cat]).exists()):
            # cocokkan dari teks terbanyak di golongan ini (ciri huruf paling bisa dipercaya)
            rep = max(bs, key=lambda b: (b.text_rect[2] * b.text_rect[3]))
            path = ""
            try:
                res = fontmatch.best_font(img, rep.text_rect, rep.src_h, top=3,
                                          include_system=bool(settings.get("font_match_system", True)),
                                          readable=True, lowercase=cat == "narration-lower")
                if res and res[0][1] <= FONT_OK:
                    path = res[0][0]
            except Exception:
                path = ""
            mem[cat] = path
            if log:
                from .typeset import font_name
                log(f"[{page.name}] font {FONT_CAT_LABEL.get(cat, cat)}: "
                    + (font_name(path) if path else "font default (tidak ada yang cukup mirip)")
                    + " · diingat untuk halaman berikutnya")
        for b in bs:
            if mem.get(cat):
                b.font = mem[cat]


def match_sfx_fonts(img, blocks, settings):
    """Teks spesial / SFX: pilih font yang bentuk hurufnya paling mirip dengan aslinya
    (font aplikasi dulu, lalu font perangkat)."""
    from . import fontmatch
    for b in blocks:
        if getattr(b, "sfx", False) and b.text_rect and not b.font:
            try:
                f = fontmatch.best_font(img, b.text_rect, b.src_h,
                                        include_system=bool(settings.get("font_match_system", True)),
                                        online=bool(settings.get("font_match_online", True)))
            except Exception:
                f = None
            if f:
                b.font = f
            try:   # miring hanya bila huruf aslinya memang miring
                feat = fontmatch.source_features(img, b.text_rect, b.src_h)
                if feat is not None:
                    b.italic = abs(feat["slant"]) > 0.15
            except Exception:
                pass


def step_ocr(page: Page, project: Project, settings: dict, progress=None, only=None):
    """only: daftar blok yang dibaca (None = semua)."""
    img = detector.load_image(page.path)
    targets = [b for b in (page.blocks if only is None else only) if b.kind != "title"]
    if targets:
        ocr.ocr_page(img, targets, settings["ocr_engine"], project.source_lang, settings["gpu"], progress)
    # kotak yang dibuat manual / belum diberi gaya: baca warna teks aslinya
    from . import textstyle
    for b in targets:
        if b.kind != "title" and not b.preset and not b.color2 and (b.color or "#000000").upper() == "#000000":
            textstyle.apply(img, b)
    # SFX yang tidak terbaca sebagai kata (mis. SFX Jepang saat sumbernya Inggris) dibiarkan apa adanya
    page.blocks = [b for b in page.blocks
                   if not getattr(b, "sfx", False) or sfx_text_ok(b.source, project.source_lang)]
    # teks bebas yang terbaca sebagai sampah (mis. SFX Jepang "ジ" saat sumbernya Inggris) dibuang
    if project.source_lang not in ("ja", "zh", "zh-tw", "ko"):
        from . import ocrfix

        def ok(b):
            if b not in targets or b.kind == "title" or not b.text_rect:
                return True                        # kotak buatan pengguna tidak pernah dibuang otomatis
            conf = getattr(b, "_ocr_conf", None)
            if conf is not None and conf < 0.15:
                return False                       # OCR sendiri tidak yakin sama sekali
            if b.kind == "free" and not free_text_ok(b.source):
                return False
            return ocrfix.plausible(b.source, project.source_lang)
        page.blocks = [b for b in page.blocks if ok(b)]
    page.status = "di-OCR"


def free_text_ok(text: str) -> bool:
    """Teks bebas (narasi kecil / gumaman) hasil OCR huruf Latin yang masuk akal."""
    t = "".join(c for c in (text or "") if not c.isspace())
    if not t:
        return False
    letters = sum(c.isalpha() and c.isascii() for c in t)
    import re
    if letters == 1 and re.fullmatch(r"[A-Za-z](\.\.\.|[!?]+|…)", t):
        return True                        # "I...", "A!"
    return letters >= 2 and letters >= 0.55 * len(t)


def sfx_text_ok(text: str, lang: str) -> bool:
    import re
    t = (text or "").strip()
    if not t:
        return False
    if lang in ("ja", "zh", "zh-tw", "ko"):
        return True
    chars = [c for c in t if not c.isspace() and c not in "!?.,…'\"-~"]
    letters = [c for c in chars if c.isalpha()]
    if len(letters) < 3 or len(letters) < 0.7 * max(1, len(chars)):
        return False
    words = re.findall(r"[A-Za-z]{2,}", t)
    return any(re.search(r"[AEIOUYaeiouy]", w) for w in words)


def translate_texts(texts, page, project: Project, settings: dict, use_cache: bool = True) -> list[str]:
    """Terjemahkan dengan skill: gaya bahasa + memori cerita (tokoh, panggilan, halaman sebelumnya)."""
    from . import skills
    glossary = dict(project.glossary)
    if settings.get("story_memory", True):
        glossary = {**skills.names_glossary(project), **glossary}    # nama tokoh dari memori cerita
    ctx, ctx_key = skills.translate_context(project, page, settings, texts)
    return translator.translate(texts, project.source_lang, project.target_lang, settings["translate_engine"],
                                settings, glossary, use_cache=use_cache, context=ctx, ctx_key=ctx_key)


def step_translate(page: Page, project: Project, settings: dict, log=None, only=None):
    for b in page.blocks:
        if b.kind == "title" and project.series_title:
            b.translation = project.series_title       # judul seri: tidak diterjemahkan ulang
    blocks = [b for b in (page.blocks if only is None else only) if b.kind != "title"]
    if not blocks:
        page.status = "diterjemah"
        return
    texts = [b.source for b in blocks]
    translator.reset_stats()
    res = translate_texts(texts, page, project, settings)
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
    for b, t in zip(blocks, res):
        b.translation = t
    page.status = "diterjemah"


def _clean_sig(b) -> tuple:
    """Hal-hal yang memengaruhi hasil hapus teks sebuah blok."""
    return (int(b.x), int(b.y), int(b.w), int(b.h), bool(b.clean), b.kind, bool(getattr(b, "sfx", False)),
            tuple(map(tuple, b.mask_poly or [])), tuple(b.text_rect or []),
            bool((b.source or "").strip()), bool((b.translation or "").strip()),
            (b.translation or "").strip() == (b.source or "").strip())


def _rect_pad(r, pad, W, H):
    x, y, w, h = r[:4]
    return max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)


def sanitize_fonts(project: Project) -> int:
    """Lepaskan font hiasan (mis. Goudy Stout) yang terpilih OTOMATIS untuk dialog / narasi di proyek
    lama -> kembali ke font default / font yang diingat. Font pilihan manual tidak diubah.
    Mengembalikan jumlah balon yang diubah."""
    from . import fontmatch
    bad = {c for c, pth in project.font_memory.items() if pth and fontmatch.is_decorative(pth)}
    for c in bad:
        del project.font_memory[c]
    n = 0
    for pg in project.pages:
        for b in pg.blocks:
            if b.font and b.font_cat and not getattr(b, "sfx", False) and fontmatch.is_decorative(b.font):
                b.font = project.font_memory.get(b.font_cat, "")
                n += 1
    return n


def mark_clean_valid(project: Project):
    """Proyek dibuka: hasil bersih yang tersimpan dianggap cocok dengan balon yang tersimpan."""
    for pg in project.pages:
        if pg.cleaned_path and Path(pg.cleaned_path).exists():
            pg._clean_sigs = {b.id: _clean_sig(b) for b in pg.blocks}


def step_clean(page: Page, settings: dict, incremental: bool = True):
    """Hapus teks. Bila hasil bersih sebelumnya masih ada, hanya balon yang BERUBAH (digeser, diubah
    ukurannya, ditambah, dihapus, dsb.) yang dibersihkan ulang -- jauh lebih cepat, terutama dengan LaMa."""
    img = detector.load_image(page.path)
    H, W = img.shape[:2]
    method = settings["clean_method"]
    sigs_new = {b.id: _clean_sig(b) for b in page.blocks}
    old = getattr(page, "_clean_sigs", None)
    cached = page.cleaned_path if page.cleaned_path and Path(page.cleaned_path).exists() else ""
    cleaned = None
    if incremental and old is not None and cached:
        base = detector.load_image(cached)
        if base is not None and base.shape == img.shape:
            changed = [bid for bid, sg in sigs_new.items() if old.get(bid) != sg]
            removed = [bid for bid in old if bid not in sigs_new]
            if not changed and not removed:
                return base
            pad = 24
            regions = []
            for bid in changed + removed:
                for sg in (old.get(bid), sigs_new.get(bid)):
                    if sg:
                        regions.append(_rect_pad(sg, pad, W, H))
            # balon lain yang bersinggungan dengan area yang dikembalikan juga dibersihkan ulang
            def hits(b):
                bx0, by0, bx1, by1 = _rect_pad((b.x, b.y, b.w, b.h), pad, W, H)
                return any(bx0 < x1 and x0 < bx1 and by0 < y1 and y0 < by1 for x0, y0, x1, y1 in regions)
            redo = [b for b in page.blocks if hits(b)]
            for b in redo:
                regions.append(_rect_pad((b.x, b.y, b.w, b.h), pad, W, H))
            for x0, y0, x1, y1 in regions:
                base[y0:y1, x0:x1] = img[y0:y1, x0:x1]
            cleaned = inpaint.clean_page(img, redo, method, base=base,
                                         patch=bool(settings.get("auto_patch", True)),
                                         lines=bool(settings.get("auto_lines", True)),
                                         bubble_blocks=page.blocks)
    if cleaned is None:
        cleaned = inpaint.clean_page(img, page.blocks, method, patch=bool(settings.get("auto_patch", True)),
                                     lines=bool(settings.get("auto_lines", True)))
    out = output_dir(page, settings) / ".cache"
    out.mkdir(exist_ok=True)
    p = out / (Path(page.path).stem + "_clean.png")
    detector.save_image(str(p), cleaned, fast=True)
    detector.remember_image(str(p), cleaned)      # dibaca lagi saat render: tak perlu decode ulang
    page.cleaned_path = str(p)
    _saved(str(p), cleaned)
    page._clean_sigs = sigs_new
    return cleaned


ON_SAVED = None        # diisi tampilan: dipanggil (path, gambar) setelah hasil disimpan


def _saved(path, img, pending=False):
    if ON_SAVED is not None:
        try:
            ON_SAVED(path, img, pending) if pending else ON_SAVED(path, img)
        except Exception:
            pass


def _title_image(b) -> str:
    f = getattr(b, "title_image", "") or ""
    return f if f and Path(f).exists() else ""


def _apply_titles(page: Page, project: Project, settings: dict, final):
    titles = [b for b in page.blocks if b.kind == "title"
              and (_title_image(b) or (b.translation or project.series_title).strip())]
    if titles:
        from . import titlelogo
        src = detector.load_image(page.path)
        for b in titles:
            rect = [b.x, b.y, b.w, b.h]
            img_f = _title_image(b)
            if img_f:              # judul buatan sendiri (gambar ditempel)
                final = titlelogo.paste_title(src, img_f, rect, titlelogo.mask_in_rect(src, rect),
                                              fit=b.title_fit or "contain", scale=float(b.title_scale or 1.0),
                                              clean=not b.title_keep_bg, onto=final)
                continue
            final = titlelogo.render_title(src, (b.translation or project.series_title).strip(), rect,
                                           titlelogo.mask_in_rect(src, rect),
                                           b.font or settings.get("font", "") or typeset.default_font(project.target_lang),
                                           upper=(b.case or ("upper" if settings.get("uppercase", True) else "none")) == "upper",
                                           onto=final)
    return final


def render_layers(page: Page, project: Project, settings: dict):
    """Untuk export PSD: (gambar bersih BGR, hasil akhir BGR, [(balon, lapisan RGBA PIL, x, y)]).
    Memakai hasil bersih yang tersimpan (tidak menghapus teks ulang)."""
    if not page.cleaned_path or not Path(page.cleaned_path).exists():
        raise ValueError(f"[{page.name}] belum dirender — terjemahkan / render halaman ini dulu.")
    base = detector.load_image(page.cleaned_path)
    if page.edits:
        from . import edits as ED
        try:
            mt = Path(page.cleaned_path).stat().st_mtime
        except OSError:
            mt = 0
        base = ED.apply_all(page, base, detector.load_image(page.path), settings["clean_method"],
                            base_key=f"{page.cleaned_path}:{mt}")
    sync_default_style(settings)
    layers: list = []
    final = typeset.render_page(base, page.blocks, project.target_lang, settings.get("font", ""),
                                settings.get("uppercase", True), int(settings.get("max_font_size", 48)),
                                italic=settings.get("italic", True),
                                default_size=int(settings.get("default_font_size", 0) or 0),
                                default_bold=bool(settings.get("default_bold", False)),
                                line_spacing=float(settings.get("line_spacing", 1.2) or 1.2), collect=layers)
    titled = _apply_titles(page, project, settings, final)
    for t in [b for b in page.blocks if b.kind == "title"]:     # logo judul seri -> lapisan sendiri
        H, W = titled.shape[:2]
        x0, y0 = max(0, int(t.x)), max(0, int(t.y))
        x1, y1 = min(W, int(t.x + t.w)), min(H, int(t.y + t.h))
        if x1 > x0 and y1 > y0:
            diff = (titled[y0:y1, x0:x1] != final[y0:y1, x0:x1]).any(axis=2)
            if diff.any():
                from PIL import Image
                crop = titled[y0:y1, x0:x1][..., ::-1]
                rgba = np.dstack([crop, (diff * 255).astype(np.uint8)])
                layers.append((t, Image.fromarray(np.ascontiguousarray(rgba), "RGBA"), x0, y0))
    return base, titled, layers


def step_render(page: Page, project: Project, settings: dict, recalc_clean: bool = False):
    if recalc_clean or not page.cleaned_path or not Path(page.cleaned_path).exists():
        base = step_clean(page, settings)
    else:
        base = detector.load_image(page.cleaned_path)
        if getattr(page, "_clean_sigs", None) is None:     # proyek baru dibuka: hasil bersih tersimpan = sah
            page._clean_sigs = {b.id: _clean_sig(b) for b in page.blocks}
    if page.edits:      # suntingan manual (healing brush, hapus area, isi warna) di atas hasil bersih
        from . import edits as ED
        try:
            mt = Path(page.cleaned_path).stat().st_mtime if page.cleaned_path else 0
        except OSError:
            mt = 0
        base = ED.apply_all(page, base, detector.load_image(page.path), settings["clean_method"],
                            base_key=f"{page.cleaned_path}:{mt}")
    sync_default_style(settings)
    final = typeset.render_page(base, page.blocks, project.target_lang, settings.get("font", ""),
                                settings.get("uppercase", True), int(settings.get("max_font_size", 48)),
                                italic=settings.get("italic", True),
                                default_size=int(settings.get("default_font_size", 0) or 0),
                                default_bold=bool(settings.get("default_bold", False)),
                                line_spacing=float(settings.get("line_spacing", 1.2) or 1.2))
    final = _apply_titles(page, project, settings, final)
    p = str(output_dir(page, settings) / output_name(page, project, settings))
    page.output_path = p
    if Path(p).exists():
        # tampilkan dari memori sekarang, file ditulis di belakang layar (bagian terlama render)
        _saved(p, final, pending=True)
        detector.save_image_later(p, final)
    else:
        detector.save_image(p, final)
        _saved(p, final)
    page.status = "selesai"
    return final


# ---------------------------------------------------------------- render langsung (saat menyunting)
# Mengetik terjemahan / mengubah gaya: hasil tampil di setiap ketikan. Gambar dasar (bersih + suntingan
# manual) disimpan di memori, hanya teks yang ditata ulang (balon lain diambil dari cache), dan tidak ada
# yang ditulis ke disk sampai pengguna berhenti menyunting (commit_live).
_LIVE_BASE: dict = {}


def can_render_live(page: Page) -> bool:
    return bool(page.cleaned_path and Path(page.cleaned_path).exists())


def _live_base(page: Page, settings: dict):
    try:
        mt = Path(page.cleaned_path).stat().st_mtime
    except OSError:
        mt = 0
    try:
        ek = hash(repr(page.edits)) if page.edits else 0
    except Exception:
        ek = id(page.edits)
    key = (page.cleaned_path, mt, ek, settings.get("clean_method"))
    hit = _LIVE_BASE.get(page.path)
    if hit is not None and hit[0] == key:
        return hit[1]
    base = detector.load_image(page.cleaned_path)
    if page.edits:
        from . import edits as ED
        base = ED.apply_all(page, base, detector.load_image(page.path), settings["clean_method"],
                            base_key=f"{page.cleaned_path}:{mt}")
    if len(_LIVE_BASE) > 3:
        _LIVE_BASE.clear()
    _LIVE_BASE[page.path] = (key, base)
    return base


def _clean_preview(page: Page, settings: dict, blocks: list, base):
    """Kotak balon sedang digeser / diubah ukurannya: hapus teks di posisi barunya SEKETIKA (cara cepat,
    tanpa AI berat) dan kembalikan gambar asli di posisi lamanya. Hasil kualitas penuh dibuat
    setelah kotak dilepas. -> (gambar, True bila ada yang dibersihkan ulang)."""
    old = getattr(page, "_clean_sigs", None)
    if old is None:
        return base, False
    new = {b.id: _clean_sig(b) for b in blocks}
    # hanya perubahan kotak (posisi/ukuran/bentuk/hapus-tidaknya) -- mengetik terjemahan tidak menghapus
    # ulang apa pun (bagian akhir sig = ada/tidaknya terjemahan)
    changed = [bid for bid, sg in new.items() if old.get(bid) is None or old[bid][:-2] != sg[:-2]]
    removed = [bid for bid in old if bid not in new]
    if not changed and not removed:
        return base, False
    img = detector.load_image(page.path)
    if img.shape != base.shape:
        return base, False
    H, W = img.shape[:2]
    pad = 24
    regions = []
    for bid in changed + removed:
        for sg in (old.get(bid), new.get(bid)):
            if sg:
                regions.append(_rect_pad(sg, pad, W, H))

    def hits(b):
        bx0, by0, bx1, by1 = _rect_pad((b.x, b.y, b.w, b.h), pad, W, H)
        return any(bx0 < x1 and x0 < bx1 and by0 < y1 and y0 < by1 for x0, y0, x1, y1 in regions)
    redo = [b for b in blocks if hits(b)]
    for b in redo:
        regions.append(_rect_pad((b.x, b.y, b.w, b.h), pad, W, H))
    out = base.copy()
    for x0, y0, x1, y1 in regions:
        out[y0:y1, x0:x1] = img[y0:y1, x0:x1]
    m = settings.get("clean_method", "auto")
    fast = m if m in ("opencv", "none") else "fill"
    return inpaint.clean_page(img, redo, fast, base=out, patch=False, lines=False, bubble_blocks=blocks), True


def render_live(page: Page, project: Project, settings: dict, blocks: list):
    """Hasil halaman di memori untuk `blocks` (salinan blok milik tampilan). Tidak menulis file.
    -> (gambar, pratinjau_hapus): pratinjau_hapus True = area teks dihapus dengan cara cepat
    (kotak sedang digeser), hasil kualitas penuh menyusul lewat render biasa."""
    base = _live_base(page, settings)
    if getattr(page, "_clean_sigs", None) is None:
        page._clean_sigs = {b.id: _clean_sig(b) for b in page.blocks}
    base, previewed = _clean_preview(page, settings, blocks, base)
    sync_default_style(settings)
    final = typeset.render_page(base, blocks, project.target_lang, settings.get("font", ""),
                                settings.get("uppercase", True), int(settings.get("max_font_size", 48)),
                                italic=settings.get("italic", True),
                                default_size=int(settings.get("default_font_size", 0) or 0),
                                default_bold=bool(settings.get("default_bold", False)),
                                line_spacing=float(settings.get("line_spacing", 1.2) or 1.2))
    return _apply_titles(page, project, settings, final), previewed


def commit_live(page: Page, project: Project, settings: dict, final):
    """Simpan hasil render langsung (dipanggil setelah pengguna berhenti menyunting sejenak)."""
    p = str(output_dir(page, settings) / output_name(page, project, settings))
    page.output_path = p
    _saved(p, final, pending=True)
    detector.save_image_later(p, final)
    page.status = "selesai"
    return p


def _auto_fonts_safe(page, project, settings, log=None, only=None):
    try:
        auto_fonts(detector.load_image(page.path), page, project, settings, log=log, only=only)
    except Exception as e:      # pencocokan font gagal tidak boleh menghentikan terjemahan
        if log:
            log(f"[{page.name}] cocokkan font dilewati: {e}")


def stage_read(page: Page, project: Project, settings: dict, log=print, keep_boxes: bool = False):
    """Tahap 1 (CPU): deteksi + OCR + cocokkan font."""
    if keep_boxes and page.blocks:
        need_ocr = [b for b in page.blocks if b.kind != "title" and not (b.source or "").strip()]
        log(f"[{page.name}] memakai {len(page.blocks)} kotak yang ada · OCR {len(need_ocr)} kotak baru…")
        if need_ocr:
            step_ocr(page, project, settings, only=need_ocr)
            _auto_fonts_safe(page, project, settings, log, only=[b for b in need_ocr if b in page.blocks])
        return
    log(f"[{page.name}] deteksi balon…")
    step_detect(page, project, settings)
    log(f"[{page.name}] {len(page.blocks)} blok ditemukan")
    if page.blocks:
        log(f"[{page.name}] OCR…")
        step_ocr(page, project, settings)
        _auto_fonts_safe(page, project, settings, log)


def stage_finish(page: Page, project: Project, settings: dict, log=print, keep_boxes: bool = False):
    """Tahap 2: terjemah (menunggu jaringan) + hapus teks & typeset (CPU)."""
    if keep_boxes:
        need_tr = [b for b in page.blocks if b.kind != "title" and (b.source or "").strip()
                   and not (b.translation or "").strip()]
        if need_tr:
            log(f"[{page.name}] menerjemahkan {len(need_tr)} kotak ({settings['translate_engine']})…")
            step_translate(page, project, settings, log, only=need_tr)
    elif page.blocks:
        log(f"[{page.name}] menerjemahkan ({settings['translate_engine']})…")
        step_translate(page, project, settings, log)
    log(f"[{page.name}] hapus teks & typeset…")
    step_render(page, project, settings, recalc_clean=True)
    log(f"[{page.name}] selesai -> {page.output_path}")


def process_page(page: Page, project: Project, settings: dict, stages=("detect", "ocr", "translate", "render"),
                 log=print, keep_boxes: bool = False):
    """keep_boxes=True: bila halaman SUDAH punya kotak (hasil deteksi atau kotak manual), kotak itu
    dipakai apa adanya (tidak dideteksi ulang). Hanya kotak yang belum punya teks yang di-OCR, dan
    hanya yang belum punya terjemahan yang diterjemahkan, jadi hasil edit tangan tidak tertimpa."""
    stages = tuple(stages)
    keep = bool(keep_boxes and page.blocks)
    if stages == ("detect", "ocr", "translate", "render"):
        stage_read(page, project, settings, log, keep)
        stage_finish(page, project, settings, log, keep)
        return
    if keep and "detect" in stages:
        stages = tuple(x for x in stages if x != "detect")
        if "ocr" in stages:
            stage_read(page, project, settings, log, True)
        if "translate" in stages or "render" in stages:
            if "render" in stages:
                stage_finish(page, project, settings, log, True)
            else:
                need_tr = [b for b in page.blocks if b.kind != "title" and (b.source or "").strip()
                           and not (b.translation or "").strip()]
                if need_tr:
                    step_translate(page, project, settings, log, only=need_tr)
        return
    if "detect" in stages:
        log(f"[{page.name}] deteksi balon…")
        step_detect(page, project, settings)
        log(f"[{page.name}] {len(page.blocks)} blok ditemukan")
    if "ocr" in stages and page.blocks:
        log(f"[{page.name}] OCR…")
        step_ocr(page, project, settings)
        _auto_fonts_safe(page, project, settings, log)
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
