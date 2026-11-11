"""Mesin terjemahan.

- google : gratis, tanpa API key (lewat deep-translator).
- deepl  : butuh API key DeepL (free/pro).
- llm    : endpoint kompatibel OpenAI — OpenAI, OpenRouter, Gemini, Groq,
           atau lokal (LM Studio / Ollama). Satu halaman diterjemahkan
           sekaligus supaya konteks antar-balon terjaga.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading

import requests

LANG_NAMES = {
    "ja": "Japanese", "ko": "Korean", "zh": "Chinese (Simplified)", "zh-tw": "Chinese (Traditional)",
    "en": "English", "id": "Indonesian", "ms": "Malay", "vi": "Vietnamese", "th": "Thai",
    "es": "Spanish", "pt": "Portuguese", "fr": "French", "de": "German", "ru": "Russian",
}

# preset endpoint LLM populer (bisa diubah di Pengaturan)
LLM_PRESETS = {
    "OpenAI": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "Gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.0-flash"),
    "OpenRouter": ("https://openrouter.ai/api/v1", "deepseek/deepseek-chat"),
    "Groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "LM Studio (lokal)": ("http://localhost:1234/v1", "local-model"),
    "Ollama (lokal)": ("http://localhost:11434/v1", "qwen2.5:7b"),
}


class TranslateError(Exception):
    pass


def apply_glossary_plain(text: str, glossary: dict) -> str:
    for src, dst in glossary.items():
        if src:
            text = text.replace(src, dst)
    return text


def translate_google(texts, src, tgt, glossary):
    from deep_translator import GoogleTranslator
    s = {"zh": "zh-CN", "zh-tw": "zh-TW"}.get(src, src)
    t = {"zh": "zh-CN", "zh-tw": "zh-TW"}.get(tgt, tgt)
    from concurrent.futures import ThreadPoolExecutor

    def one(txt):
        if not txt.strip():
            return ""
        # satu penerjemah per permintaan (aman dipakai bersamaan)
        return GoogleTranslator(source=s, target=t).translate(apply_glossary_plain(txt, glossary)) or ""

    if len(texts) <= 1:
        return [one(x) for x in texts]
    # beberapa permintaan sekaligus: menunggu jaringan, bukan CPU -> jauh lebih cepat, tetap ringan
    with ThreadPoolExecutor(max_workers=min(4, len(texts))) as ex:
        return list(ex.map(one, texts))


def translate_deepl(texts, src, tgt, glossary, api_key):
    if not api_key:
        raise TranslateError("API key DeepL belum diisi di Pengaturan.")
    host = "api-free.deepl.com" if api_key.endswith(":fx") else "api.deepl.com"
    payload = {
        "text": [apply_glossary_plain(t, glossary) or " " for t in texts],
        "source_lang": src.split("-")[0].upper(),
        "target_lang": {"en": "EN-US", "pt": "PT-BR", "zh": "ZH-HANS", "zh-tw": "ZH-HANT"}.get(tgt, tgt.upper()),
    }
    r = requests.post(f"https://{host}/v2/translate", json=payload,
                      headers={"Authorization": f"DeepL-Auth-Key {api_key}"}, timeout=60)
    if r.status_code != 200:
        raise TranslateError(f"DeepL error {r.status_code}: {r.text[:200]}")
    return [t["text"] for t in r.json()["translations"]]


# Prompt dibuat ringkas: dikirim di SETIAP permintaan, jadi tiap kata = token yang dibayar.
SYSTEM_PROMPT = ("Translate manga speech bubbles {src}->{tgt}. Natural, concise dialogue; keep tone & "
                 "character voice; short SFX. Items are one page in reading order (use as "
                 "context). Source text comes from OCR and may contain misread letters (e.g. G/C, I/l/!, 0/O); "
                 "silently fix obvious OCR mistakes before translating. {natural}{glossary}{context}{extra}{fmt}")

PROMPT_VERSION = "p2"

FORMAT_RULE = ("Reply JSON only: {\"id\":\"translation\"} (same ids as the input). "
               "This output format overrides any other format mentioned above.")

# Arahan bahasa sehari-hari per bahasa tujuan (supaya hasil tidak kaku "bahasa AI").
NATURAL = {
    "id": ("Write Indonesian the way real fans talk in scanlations, not textbook Indonesian: casual spoken "
           "forms (nggak, udah, aja, banget, kok, sih, dong, deh, kan) where they fit the character; aku/kamu or "
           "gue/lo instead of saya/Anda unless the speaker is formal; avoid stiff words (Anda, tersebut, apakah, "
           "sangatlah, oleh karena itu, merupakan); never translate word-for-word. "),
}

_VARS = {
    "tgt": ("targetlanguage", "target_language", "target language", "targetlang", "target", "tgt", "bahasatujuan"),
    "src": ("sourcelanguage", "source_language", "source language", "sourcelang", "source", "src", "bahasaasal"),
}


def fill_vars(text: str, src: str, tgt: str) -> str:
    """Isi variabel di prompt buatan sendiri: {targetLanguage}, {sourceLanguage}, {{tgt}}, [target] …"""
    names = {"tgt": LANG_NAMES.get(tgt, tgt), "src": LANG_NAMES.get(src, src)}

    def rep(m):
        key = re.sub(r"[\s_-]", "", m.group(2).lower())
        for k, alts in _VARS.items():
            if key in {re.sub(r"[\s_-]", "", a) for a in alts}:
                return names[k]
        return m.group(0)
    return re.sub(r"(\{\{|\{|\[)\s*([A-Za-z][A-Za-z _-]{1,24}?)\s*(\}\}|\}|\])", rep, text or "")


def is_full_prompt(extra: str) -> bool:
    """Instruksi panjang / berbentuk persona ('You are…', 'Kamu adalah…') = system prompt utuh milik pengguna."""
    e = (extra or "").strip()
    return len(e) > 400 or bool(re.match(r"(?i)(you are|act as|kamu adalah|anda adalah|kamu ialah|role\s*:)", e))


def build_system(src: str, tgt: str, glossary_txt: str = "", context: str = "", extra: str = "") -> str:
    """Susun system prompt. Instruksi pengguna diberi prioritas tertinggi:
    - persona / prompt panjang -> dipakai sebagai prompt utama (variabel diisi), aturan dasar jadi catatan;
    - instruksi pendek -> ditaruh di AKHIR dengan label prioritas.
    Format JSON selalu di paling akhir supaya tidak tertimpa format dari prompt pengguna."""
    S, T = LANG_NAMES.get(src, src), LANG_NAMES.get(tgt, tgt)
    nat = NATURAL.get((tgt or "").split("-")[0], "")
    if "standard formal" in (context or ""):      # Gaya bahasa: Baku -> jangan dipaksa santai
        nat = ""
    ctx = (context.strip() + " ") if context.strip() else ""
    extra = fill_vars((extra or "").strip(), src, tgt)
    if extra and is_full_prompt(extra):
        return (extra + "\n\n--- Task ---\nTranslate the manga speech bubbles below from " + S + " to " + T +
                ". Items are one page in reading order (use as context). Text comes from OCR: silently fix "
                "obvious misread letters. Follow the instructions above first; they have the highest priority. "
                + nat + glossary_txt + ctx + "\n" + FORMAT_RULE)
    user_rule = ("USER INSTRUCTIONS (highest priority, override the defaults above): "
                 + extra.rstrip(".") + ". ") if extra else ""
    return SYSTEM_PROMPT.format(src=S, tgt=T, natural=nat, glossary=glossary_txt, context=ctx,
                                extra=user_rule, fmt=FORMAT_RULE)


def _glossary_for(texts, glossary):
    """Hanya istilah glosarium yang benar-benar muncul di teks (hemat token)."""
    joined = "\n".join(texts)
    used = {k: v for k, v in (glossary or {}).items() if k and k in joined}
    return ("Glossary: " + "; ".join(f"{k}={v}" for k, v in used.items()) + ". ") if used else ""


def _chat(base_url, api_key, model, system, user, temperature=0.3, timeout=180) -> str:
    if not base_url:
        raise TranslateError("Base URL LLM belum diisi (Pengaturan → Terjemahan → LLM).")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {"model": model, "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    r = requests.post(base_url.rstrip("/") + "/chat/completions", json=body, headers=headers, timeout=timeout)
    if r.status_code != 200:
        raise TranslateError(f"LLM error {r.status_code}: {r.text[:300]}")
    js = r.json()
    usage = js.get("usage") or {}
    STATS["tokens_in"] += int(usage.get("prompt_tokens") or 0)
    STATS["tokens_out"] += int(usage.get("completion_tokens") or 0)
    return js["choices"][0]["message"]["content"] or ""


def llm_chat(settings: dict, system: str, user: str, temperature: float = 0.3) -> str:
    """Satu permintaan ke LLM yang diatur di Pengaturan (dipakai skill: memori, proofread)."""
    return _chat(settings.get("llm_base_url", ""), settings.get("llm_api_key", ""), settings.get("llm_model", ""),
                 system, user, temperature)


def translate_llm(texts, src, tgt, glossary, base_url, api_key, model, extra_prompt="", temperature=0.3,
                  context=""):
    items = [t for t in texts if t.strip()]
    if not items:
        return ["" for _ in texts]
    sys = build_system(src, tgt, _glossary_for(items, glossary), context, extra_prompt)
    numbered = {str(i + 1): t for i, t in enumerate(texts) if t.strip()}
    user = json.dumps(numbered, ensure_ascii=False, separators=(",", ":"))   # JSON padat, tanpa spasi
    content = _chat(base_url, api_key, model, sys, user, temperature)
    data = _parse_json(content)
    return [str(data.get(str(i + 1), "")) if texts[i].strip() else "" for i in range(len(texts))]


def parse_json(content: str) -> dict:
    return _parse_json(content)


def _parse_json(content: str) -> dict:
    content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        raise TranslateError(f"Balasan LLM bukan JSON: {content[:200]}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise TranslateError(f"JSON LLM rusak: {e}")


# ---------------------------------------------------------------- cache & penghematan

STATS = {"sent": 0, "cached": 0, "skipped": 0, "dupes": 0, "tokens_in": 0, "tokens_out": 0}
_cache: dict | None = None
_lock = threading.Lock()
CACHE_MAX = 20000


def _cache_path():
    from .paths import data_dir
    return data_dir() / "translation_cache.json"


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(_cache_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache = {}
    return _cache


def _save_cache():
    with _lock:
        c = _load_cache()
        if len(c) > CACHE_MAX:                       # buang entri tertua
            for k in list(c)[: len(c) - CACHE_MAX]:
                del c[k]
        tmp = _cache_path().with_suffix(".tmp")
        tmp.write_text(json.dumps(c, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(_cache_path())


def clear_cache():
    global _cache
    with _lock:
        _cache = {}
        try:
            _cache_path().unlink()
        except OSError:
            pass


def cache_info() -> tuple[int, int]:
    """(jumlah entri, ukuran byte)"""
    p = _cache_path()
    return len(_load_cache()), (p.stat().st_size if p.exists() else 0)


def _key(engine, settings, src, tgt, glossary, text, ctx_key=""):
    model = settings.get("llm_model", "") if engine == "llm" else ""
    extra = settings.get("llm_extra_prompt", "") if engine == "llm" else ""
    if ctx_key:      # gaya bahasa / memori cerita ikut menentukan hasil LLM
        extra += "\x1e" + ctx_key
    gl = json.dumps(sorted((k, v) for k, v in (glossary or {}).items() if k in text), ensure_ascii=False)
    if engine == "llm":
        extra = PROMPT_VERSION + extra      # prompt bawaan berubah -> hasil lama dari cache tidak dipakai
    raw = "\x1f".join([engine, model, extra, src, tgt, gl, text])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def needs_translation(text: str) -> bool:
    """Teks tanpa huruf (…, !?, ---, angka) tidak perlu dikirim ke mesin penerjemah."""
    return any(ch.isalpha() for ch in text)


def reset_stats():
    for k in STATS:
        STATS[k] = 0


def _raw_translate(texts, src, tgt, engine, settings, glossary, context=""):
    if engine == "google":
        return translate_google(texts, src, tgt, glossary)
    if engine == "deepl":
        return translate_deepl(texts, src, tgt, glossary, settings.get("deepl_key", ""))
    if engine == "llm":
        return translate_llm(texts, src, tgt, glossary,
                             settings.get("llm_base_url", ""), settings.get("llm_api_key", ""),
                             settings.get("llm_model", ""), settings.get("llm_extra_prompt", ""),
                             float(settings.get("llm_temperature", 0.3)), context=context)
    raise TranslateError(f"Engine terjemahan tidak dikenal: {engine}")


def translate(texts: list[str], src: str, tgt: str, engine: str, settings: dict, glossary: dict | None = None,
              use_cache: bool = True, context: str = "", ctx_key: str = ""):
    """Terjemahkan daftar teks dengan hemat:
    - teks kosong / hanya tanda baca tidak dikirim (disalin apa adanya),
    - teks yang sama di satu halaman dikirim sekali,
    - teks yang pernah diterjemahkan diambil dari cache (bila use_cache)."""
    glossary = glossary or {}
    out = [""] * len(texts)
    todo: dict[str, list[int]] = {}
    cache = _load_cache() if use_cache and settings.get("translation_cache", True) else None
    for i, t in enumerate(texts):
        t = (t or "").strip()
        if not t:
            continue
        if not needs_translation(t):
            out[i] = t
            STATS["skipped"] += 1
            continue
        if cache is not None:
            hit = cache.get(_key(engine, settings, src, tgt, glossary, t, ctx_key))
            if hit is not None:
                out[i] = hit
                STATS["cached"] += 1
                continue
        if t in todo:
            STATS["dupes"] += 1
        todo.setdefault(t, []).append(i)
    if todo:
        uniq = list(todo)
        res = _raw_translate(uniq, src, tgt, engine, settings, glossary, context)
        STATS["sent"] += len(uniq)
        store = settings.get("translation_cache", True)
        with _lock:
            c = _load_cache()
            for t, tr in zip(uniq, res):
                for i in todo[t]:
                    out[i] = tr
                if store and tr:
                    c[_key(engine, settings, src, tgt, glossary, t, ctx_key)] = tr
        if store:
            try:
                _save_cache()
            except OSError:
                pass
    return out
