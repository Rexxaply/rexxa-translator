"""Skill AI & alat tambahan:

- Memori cerita : daftar tokoh (nama, nama di raw, gender, cara memanggil, gaya bicara, catatan)
                  + catatan cerita. Dikirim ke LLM saat menerjemahkan, nama tokoh juga dipakai
                  sebagai glosarium untuk Google/DeepL. Disimpan per proyek DAN per seri
                  (otomatis dipakai lagi di chapter berikutnya dengan judul seri yang sama).
- Gaya bahasa   : santai / gaul / baku / kocak / dramatis + honorifik dipertahankan / diterjemahkan.
- Proofread     : cek lokal (tanpa internet) + cek AI (LLM) dengan saran perbaikan.
- Kredit        : halaman kredit tim + watermark saat export.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import translator
from .models import Project

# ================================================================ gaya bahasa
STYLES = {
    "alami": ("Alami (bawaan)", ""),
    "santai": ("Santai sehari-hari",
               "Register: casual everyday spoken {tgt}, like real friends talking; avoid stiff formal words."),
    "gaul": ("Gaul / slang",
             "Register: trendy youthful slang of {tgt} where it fits the character (for Indonesian e.g. "
             "gue/lo, banget, nggak, udah, sih, dong); keep it readable."),
    "baku": ("Baku / formal", "Register: proper standard formal {tgt} grammar and vocabulary."),
    "kocak": ("Kocak", "Tone: punchy and funny in comedic scenes, playful word choice; keep the meaning."),
    "dramatis": ("Dramatis", "Tone: expressive, emotional, slightly literary {tgt} for dramatic scenes."),
}
HONORIFICS = {
    "keep": ("Pertahankan (-san, senpai, oppa…)",
             "Keep honorifics and name suffixes as-is (-san, -kun, -chan, senpai, oppa, hyung, gege…)."),
    "translate": ("Terjemahkan (kak, bang, pak…)",
                  "Replace honorifics/suffixes with natural {tgt} forms of address (for Indonesian e.g. kak, "
                  "bang, mas, mbak, pak, bu, dik); do not keep -san/-kun/senpai/oppa."),
}


def style_prompt(settings: dict, tgt: str) -> str:
    t = translator.LANG_NAMES.get(tgt, tgt)
    parts = []
    st = STYLES.get(settings.get("tl_style", "alami"), STYLES["alami"])[1]
    if st:
        parts.append(st.format(tgt=t))
    hn = HONORIFICS.get(settings.get("tl_honorific", "keep"), HONORIFICS["keep"])[1]
    parts.append(hn.format(tgt=t))
    return " ".join(parts)


# ================================================================ memori cerita
CHAR_FIELDS = ("name", "source", "gender", "call", "speech", "notes")
GENDERS = ["", "laki-laki", "perempuan", "lainnya"]


def story_of(project: Project) -> dict:
    s = project.story or {}
    return {"characters": [dict({k: "" for k in CHAR_FIELDS}, **{k: str(v or "") for k, v in c.items()
                                                                 if k in CHAR_FIELDS})
                           for c in s.get("characters", []) if isinstance(c, dict)],
            "notes": str(s.get("notes", "") or "")}


def has_memory(project: Project) -> bool:
    s = story_of(project)
    return bool(s["characters"] or s["notes"].strip())


def _appears(c: dict, text: str) -> bool:
    low = text.lower()
    for k in ("name", "source"):
        for n in re.split(r"[,/;]", c.get(k, "")):
            n = n.strip()
            if len(n) >= 2 and n.lower() in low:
                return True
    return False


def memory_prompt(project: Project, texts: list[str]) -> str:
    s = story_of(project)
    chars = [c for c in s["characters"] if c["name"].strip()]
    joined = "\n".join(texts)
    if len(chars) > 12:      # banyak tokoh: kirim yang muncul di halaman ini dulu (hemat token)
        seen = [c for c in chars if _appears(c, joined)]
        chars = (seen + [c for c in chars if c not in seen])[:12]
    out = []
    if chars:
        rows = []
        for c in chars:
            bits = []
            if c["source"].strip() and c["source"].strip() != c["name"].strip():
                bits.append(f"raw: {c['source'].strip()}")
            if c["gender"]:
                bits.append({"laki-laki": "male", "perempuan": "female"}.get(c["gender"], c["gender"]))
            if c["call"].strip():
                bits.append(f"address/pronouns: {c['call'].strip()}")
            if c["speech"].strip():
                bits.append(f"speech: {c['speech'].strip()}")
            if c["notes"].strip():
                bits.append(c["notes"].strip())
            rows.append(c["name"].strip() + (f" ({'; '.join(bits)})" if bits else ""))
        out.append("Characters (use these names, genders and forms of address consistently): " + " | ".join(rows) + ".")
    if s["notes"].strip():
        n = " ".join(s["notes"].split())
        out.append("Story notes: " + n + ("" if n.endswith((".", "!", "?")) else "."))
    return " ".join(out)


def names_glossary(project: Project) -> dict:
    """{nama di raw: nama terjemahan} untuk mesin non-LLM (Google/DeepL)."""
    g = {}
    for c in story_of(project)["characters"]:
        src, name = c["source"].strip(), c["name"].strip()
        if src and name and src != name:
            for part in re.split(r"[,/;]", src):
                if part.strip():
                    g[part.strip()] = name
    return g


def memory_key(project: Project, settings: dict) -> str:
    """Bagian kunci cache: terjemahan LLM dihitung ulang bila memori / gaya berubah."""
    return json.dumps([story_of(project), settings.get("tl_style", "alami"),
                       settings.get("tl_honorific", "keep")], ensure_ascii=False, sort_keys=True)


def prev_context(project: Project, page, n: int = 6) -> str:
    """Beberapa baris terakhir halaman sebelumnya (sumber => terjemahan) supaya percakapan nyambung."""
    try:
        i = project.pages.index(page)
    except ValueError:
        return ""
    for j in range(i - 1, max(-1, i - 3), -1):
        rows = [(b.source.strip(), b.translation.strip()) for b in project.pages[j].blocks
                if b.kind != "title" and (b.source or "").strip() and (b.translation or "").strip()]
        if rows:
            rows = rows[-n:]
            return "Previous page ended with: " + " / ".join(f"{a} => {b}" for a, b in rows)[:700] + "."
    return ""


def translate_context(project: Project, page, settings: dict, texts: list[str]) -> tuple[str, str]:
    """(teks konteks untuk prompt LLM, kunci cache). Kosong untuk Google/DeepL."""
    if settings.get("translate_engine") != "llm":
        return "", ""
    parts = [style_prompt(settings, project.target_lang)]
    if settings.get("story_memory", True):
        parts.append(memory_prompt(project, texts))
        if settings.get("story_context", True) and page is not None:
            parts.append(prev_context(project, page))
    return " ".join(p for p in parts if p), memory_key(project, settings)


# ---------------------------------------------------------------- simpan per seri
def series_key(project: Project) -> str:
    t = (project.series_title or (project.export_meta or {}).get("series") or "").strip()
    if not t and project.pages:
        t = Path(project.pages[0].path).parent.parent.name
    return t


def _series_file(key: str) -> Path:
    from .paths import data_dir
    d = data_dir() / "series"
    d.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", key).strip()[:100] or "tanpa-judul"
    return d / f"{safe}.json"


def save_series(project: Project):
    key = series_key(project)
    if not key or not has_memory(project):
        return
    data = dict(story_of(project), series=key)
    _series_file(key).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_series(project: Project) -> bool:
    """Bila proyek belum punya memori: ambil memori seri yang sama. True bila dimuat."""
    if has_memory(project):
        return False
    key = series_key(project)
    if not key:
        return False
    f = _series_file(key)
    if not f.exists():
        return False
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    project.story = {"characters": d.get("characters", []), "notes": d.get("notes", "")}
    return has_memory(project)


def merge_story(old: dict, new: dict) -> dict:
    out = {"characters": [dict(c) for c in old.get("characters", [])], "notes": old.get("notes", "")}
    by = {c.get("name", "").strip().lower(): c for c in out["characters"] if c.get("name")}
    for c in new.get("characters", []) or []:
        if not isinstance(c, dict) or not str(c.get("name", "")).strip():
            continue
        c = {k: str(c.get(k, "") or "").strip() for k in CHAR_FIELDS}
        if c["gender"] not in GENDERS:
            g = c["gender"].lower()
            c["gender"] = "laki-laki" if g.startswith(("m", "l", "co")) else "perempuan" if g.startswith(
                ("f", "p", "ce", "w")) else ""
        cur = by.get(c["name"].lower())
        if cur:
            for k in CHAR_FIELDS:
                if not str(cur.get(k, "")).strip() and c[k]:
                    cur[k] = c[k]
        else:
            out["characters"].append(c)
            by[c["name"].lower()] = c
    nn = str(new.get("notes", "") or "").strip()
    if nn and nn not in out["notes"]:
        out["notes"] = (out["notes"].strip() + "\n" + nn).strip()
    return out


LEARN_PROMPT = (
    "You read a manga chapter translation ({src}->{tgt}) and build a character memory for future "
    "chapters. From the lines, list the named characters: name (as used in the {tgt} translation), "
    "source (name as written in the raw text), gender (\"laki-laki\"/\"perempuan\"/\"\" if unknown), "
    "call (how they refer to themselves and others, e.g. 'aku/kamu', 'gue/lo', calls X 'kak'), "
    "speech (short speech style), notes (relationships, max 12 words). Write call/speech/notes in "
    "Indonesian. Also short story notes (setting, terms; max 40 words, Indonesian). Do not invent "
    "facts that are not supported by the text. Reply JSON only: "
    "{{\"characters\":[{{\"name\":\"\",\"source\":\"\",\"gender\":\"\",\"call\":\"\",\"speech\":\"\",\"notes\":\"\"}}],"
    "\"notes\":\"\"}}")


def chapter_lines(project: Project, limit_chars: int = 9000) -> str:
    rows = []
    for i, p in enumerate(project.pages, 1):
        for b in p.blocks:
            if b.kind == "title" or not (b.source or "").strip():
                continue
            rows.append(f"p{i}: {b.source.strip()} => {(b.translation or '').strip()}")
    text = "\n".join(rows)
    return text[:limit_chars]


def learn(project: Project, settings: dict) -> dict:
    """Minta LLM menyusun memori tokoh dari chapter ini; hasil DIGABUNG dengan memori yang ada."""
    lines = chapter_lines(project)
    if not lines.strip():
        raise ValueError("Belum ada teks hasil OCR / terjemahan di chapter ini.")
    sysm = LEARN_PROMPT.format(src=translator.LANG_NAMES.get(project.source_lang, project.source_lang),
                               tgt=translator.LANG_NAMES.get(project.target_lang, project.target_lang))
    cur = story_of(project)
    user = ("Existing memory: " + json.dumps(cur, ensure_ascii=False) + "\n\nLines:\n" + lines) if (
        cur["characters"] or cur["notes"]) else "Lines:\n" + lines
    data = translator.parse_json(translator.llm_chat(settings, sysm, user, temperature=0.2))
    return merge_story(cur, data)


# ================================================================ proofread
def _norm_spaces(t: str) -> str:
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\s+([,.!?…;:])", r"\1", t)
    t = re.sub(r"([,;:])(?=[^\s\d.,!?…\"')\]])", r"\1 ", t)
    t = re.sub(r"\b(\w+)( \1\b)+", r"\1", t, flags=re.I)        # kata dobel "yang yang"
    return t.strip()


def local_checks(project: Project, pages: list[int] | None = None) -> list[dict]:
    """Masalah yang bisa dicek tanpa internet. Item: page, block (id), num, kind, msg, fix."""
    out = []
    idxs = pages if pages is not None else range(len(project.pages))
    names = [c for c in story_of(project)["characters"] if c["source"].strip() and c["name"].strip()]
    same_lang = project.source_lang == project.target_lang
    for pi in idxs:
        p = project.pages[pi]
        for n, b in enumerate(p.blocks, 1):
            if b.kind == "title":
                continue
            src, tl = (b.source or "").strip(), (b.translation or "").strip()

            def add(kind, msg, fix=""):
                out.append({"page": pi, "block": b.id, "num": n, "kind": kind, "msg": msg,
                            "fix": fix, "src": src, "tl": tl})

            if not src and not tl:
                continue
            if src and not tl:
                if any(ch.isalpha() for ch in src):
                    add("kosong", "Belum diterjemahkan")
                continue
            if not same_lang and tl == src and sum(ch.isalpha() for ch in src) >= 4:
                add("sama", "Terjemahan sama persis dengan teks asli")
            fixed = _norm_spaces(tl)
            if fixed != tl:
                add("ketik", "Spasi / tanda baca / kata dobel", fixed)
            if src.rstrip().endswith(("?", "？")) and not tl.rstrip().endswith(("?", "?!", "!?")) \
                    and "?" not in tl:
                add("tanda", "Teks asli bertanya (?) tapi terjemahan tidak")
            if b.fit_size and b.src_h and b.kind == "bubble" and not getattr(b, "sfx", False) \
                    and not b.font_size and b.fit_size < max(10, 0.62 * b.src_h):
                add("panjang", f"Teks kepanjangan untuk balon: huruf mengecil jadi {b.fit_size}px "
                               f"(teks asli ±{b.src_h}px). Coba persingkat.")
            for c in names:
                for raw in re.split(r"[,/;]", c["source"]):
                    raw = raw.strip()
                    if len(raw) >= 2 and raw in src and c["name"].lower() not in tl.lower() \
                            and raw.lower() not in tl.lower():
                        add("nama", f"Nama '{c['name']}' ada di teks asli tapi tidak ada di terjemahan")
                        break
    return out


PROOF_PROMPT = (
    "You are a strict proofreader for a manga translation {src}->{tgt}. Check each item (src = OCR "
    "source, tl = current translation, max = rough character budget of the bubble): mistranslation, "
    "missing meaning, unnatural or stiff {tgt}, typos/spelling, wrong or inconsistent names, genders or "
    "forms of address, and text too long for the bubble. {ctx}Only report items that really need a "
    "change. 'issue' = short explanation in Indonesian; 'fix' = the full corrected translation. "
    "Reply JSON only: {{\"id\":{{\"issue\":\"\",\"fix\":\"\"}}}} or {{}} if everything is fine.")


def _budget(b) -> int:
    from .typeset import text_area
    try:
        x, y, w, h = text_area(b)
    except Exception:
        w, h = b.w, b.h
    size = max(10, int((b.src_h or 18) * 0.95))
    per_line = max(4, int(w / (size * 0.6)))
    lines = max(1, int(h / (size * 1.2)))
    return per_line * lines


def ai_review(project: Project, settings: dict, page_index: int) -> list[dict]:
    """Proofread satu halaman dengan LLM. Item sama seperti local_checks (kind = 'ai')."""
    p = project.pages[page_index]
    items, blocks = {}, {}
    for n, b in enumerate(p.blocks, 1):
        if b.kind == "title" or not (b.translation or "").strip():
            continue
        items[str(n)] = {"src": (b.source or "").strip(), "tl": b.translation.strip(), "max": _budget(b)}
        blocks[str(n)] = (n, b)
    if not items:
        return []
    ctx = " ".join(x for x in (style_prompt(settings, project.target_lang),
                               memory_prompt(project, [v["src"] for v in items.values()])) if x)
    sysm = PROOF_PROMPT.format(src=translator.LANG_NAMES.get(project.source_lang, project.source_lang),
                               tgt=translator.LANG_NAMES.get(project.target_lang, project.target_lang),
                               ctx=(ctx + " ") if ctx else "")
    data = translator.parse_json(translator.llm_chat(settings, sysm, json.dumps(items, ensure_ascii=False),
                                                     temperature=0.1))
    out = []
    for k, v in data.items():
        if k not in blocks or not isinstance(v, dict):
            continue
        n, b = blocks[k]
        fix = str(v.get("fix", "") or "").strip()
        issue = str(v.get("issue", "") or "").strip()
        if not issue and (not fix or fix == b.translation.strip()):
            continue
        out.append({"page": page_index, "block": b.id, "num": n, "kind": "ai", "msg": issue or "Saran AI",
                    "fix": fix if fix != b.translation.strip() else "", "src": b.source or "",
                    "tl": b.translation})
    return out


# ================================================================ kredit & watermark
DEFAULT_CREDITS = {
    "page": False, "position": "end", "team": "", "roles": "Penerjemah: \nEditor: \nTypesetter: ",
    "message": "Terima kasih sudah membaca!", "logo": "", "dark": False,
    "watermark": False, "wm_text": "", "wm_pos": "br", "wm_opacity": 45, "wm_size": 2.2,
}
WM_POS = {"br": "Kanan bawah", "bl": "Kiri bawah", "tr": "Kanan atas", "tl": "Kiri atas", "c": "Tengah"}


def credits_cfg(settings: dict) -> dict:
    return dict(DEFAULT_CREDITS, **(settings.get("credits") or {}))


def _font(size: int, bold=True):
    from PIL import ImageFont
    from . import typeset
    path = typeset.default_font("id")
    try:
        return ImageFont.truetype(path, size) if path else ImageFont.load_default(size)
    except Exception:
        try:
            return ImageFont.load_default(size)
        except TypeError:
            return ImageFont.load_default()


def credit_page(cfg: dict, size: tuple[int, int], meta: dict | None = None):
    """Gambar halaman kredit (PIL RGB) seukuran halaman chapter."""
    from PIL import Image, ImageDraw
    meta = meta or {}
    W, H = size
    bg, fg, dim = ((24, 24, 28), (240, 240, 244), (160, 162, 172)) if cfg.get("dark") else \
        ((255, 255, 255), (20, 20, 24), (110, 112, 120))
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    u = max(10, int(min(W, H * 0.75) / 22))           # satuan ukuran
    blocks = []                                        # (jenis, isi, ukuran, warna)
    logo = None
    if cfg.get("logo") and Path(cfg["logo"]).exists():
        try:
            logo = Image.open(cfg["logo"]).convert("RGBA")
            logo.thumbnail((int(W * 0.5), int(H * 0.22)))
        except Exception:
            logo = None
    series = (meta.get("series") or "").strip()
    ch = (meta.get("chapter") or "").strip()
    if series:
        blocks.append(("t", series, int(u * 1.5), fg))
    if ch or meta.get("chapter_title"):
        blocks.append(("t", " · ".join(x for x in (f"Chapter {ch}" if ch else "", meta.get("chapter_title", ""))
                                       if x), int(u * 0.95), dim))
    blocks.append(("gap", "", u, None))
    for line in (cfg.get("roles") or "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            if v.strip():
                blocks.append(("role", (k.strip(), v.strip()), u, fg))
        elif line.strip():
            blocks.append(("t", line.strip(), u, fg))
    if cfg.get("team", "").strip():
        blocks.append(("gap", "", u, None))
        blocks.append(("t", cfg["team"].strip(), int(u * 1.2), fg))
    if cfg.get("message", "").strip():
        blocks.append(("gap", "", u, None))
        for line in cfg["message"].strip().splitlines():
            blocks.append(("t", line, int(u * 0.9), dim))

    def wrap(text, f, maxw):
        words, lines, cur = text.split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) <= maxw or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
        return lines + ([cur] if cur else [])

    rows = []                                          # (gambar baris: fungsi, tinggi)
    maxw = int(W * 0.84)
    for kind, val, sz, col in blocks:
        if kind == "gap":
            rows.append((None, int(sz * 0.9)))
            continue
        if kind == "role":
            fk, fv = _font(int(sz * 0.72)), _font(sz)
            rows.append((("small", val[0].upper(), fk, dim), int(sz * 0.95)))
            for ln in wrap(val[1], fv, maxw):
                rows.append((("text", ln, fv, col), int(sz * 1.3)))
            rows.append((None, int(sz * 0.45)))
            continue
        f = _font(sz)
        for ln in wrap(val, f, maxw):
            rows.append((("text", ln, f, col), int(sz * 1.3)))
    total = sum(h for _, h in rows) + (logo.height + u if logo else 0)
    y = max(u, (H - total) // 2)
    if logo:
        im.paste(logo, ((W - logo.width) // 2, y), logo)
        y += logo.height + u
    for r, h in rows:
        if r:
            _k, text, f, col = r
            d.text((W // 2, y + h // 2), text, font=f, fill=col, anchor="mm")
        y += h
    return im


def watermark(im, cfg: dict):
    """Tempel teks watermark semi-transparan (PIL Image -> PIL RGB)."""
    from PIL import Image, ImageDraw
    text = (cfg.get("wm_text") or cfg.get("team") or "").strip()
    if not text:
        return im.convert("RGB")
    base = im.convert("RGBA")
    W, H = base.size
    sz = max(10, int(min(W, 2000) * float(cfg.get("wm_size", 2.2)) / 100))
    f = _font(sz)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    tw, th = d.textlength(text, font=f), sz
    m = int(sz * 0.8)
    pos = cfg.get("wm_pos", "br")
    x = {"bl": m, "tl": m, "c": (W - tw) / 2}.get(pos, W - tw - m)
    y = {"tr": m, "tl": m, "c": (H - th) / 2}.get(pos, H - th - m * 1.4)
    a = int(255 * max(5, min(100, int(cfg.get("wm_opacity", 45)))) / 100)
    d.text((x, y), text, font=f, fill=(255, 255, 255, a), stroke_width=max(1, sz // 9),
           stroke_fill=(0, 0, 0, a))
    return Image.alpha_composite(base, layer).convert("RGB")


def apply_credits(files: list[str], cfg: dict, meta: dict, tmpdir: str, kind: str = "manga",
                  use_page: bool = True, use_wm: bool = True) -> list[str]:
    """Kembalikan daftar file baru: watermark (salinan sementara) + halaman kredit di awal/akhir."""
    from PIL import Image
    out = list(files)
    tmp = Path(tmpdir)
    tmp.mkdir(parents=True, exist_ok=True)
    if use_wm and cfg.get("watermark") and (cfg.get("wm_text") or cfg.get("team")):
        new = []
        for i, f in enumerate(out):
            with Image.open(f) as im:
                p = tmp / f"wm_{i:04d}.png"
                watermark(im, cfg).save(p)
            new.append(str(p))
        out = new
    if use_page and cfg.get("page") and out:
        sizes = []
        for f in out[:12]:
            with Image.open(f) as im:
                sizes.append(im.size)
        ws = sorted(s[0] for s in sizes)
        W = ws[len(ws) // 2]
        if kind == "manga":
            hs = sorted(s[1] for s in sizes)
            H = hs[len(hs) // 2]
        else:
            H = int(W * 1.4)
        page = tmp / "kredit.png"
        credit_page(cfg, (W, H), meta).save(page)
        pos = cfg.get("position", "end")
        if pos in ("start", "both"):
            out = [str(page)] + out
        if pos in ("end", "both"):
            out = out + [str(page)]
    return out
