"""Mesin terjemahan.

- google : gratis, tanpa API key (lewat deep-translator).
- deepl  : butuh API key DeepL (free/pro).
- llm    : endpoint kompatibel OpenAI — OpenAI, OpenRouter, Gemini, Groq,
           atau lokal (LM Studio / Ollama). Satu halaman diterjemahkan
           sekaligus supaya konteks antar-balon terjaga.
"""
from __future__ import annotations

import json
import re

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
    tr = GoogleTranslator(source=s, target=t)
    out = []
    for txt in texts:
        if not txt.strip():
            out.append("")
            continue
        out.append(tr.translate(apply_glossary_plain(txt, glossary)) or "")
    return out


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


SYSTEM_PROMPT = """You are a professional manga/manhwa translator and scanlation editor.
Translate each numbered speech bubble from {src} to {tgt}.
Rules:
- Keep the tone, character voice and emotion; make it sound natural like real dialogue, not literal.
- Bubbles are in reading order and belong to the same page; use them as context.
- Keep honorifics (-san, -kun, senpai) unless the target language naturally drops them.
- Keep sound effects short. If a bubble is only punctuation (…, !?), keep it.
- Keep it concise so it fits inside a speech bubble.
{glossary}{extra}
Reply ONLY with a JSON object mapping each number to its translation, e.g. {{"1": "...", "2": "..."}}."""


def translate_llm(texts, src, tgt, glossary, base_url, api_key, model, extra_prompt="", temperature=0.3):
    if not base_url:
        raise TranslateError("Base URL LLM belum diisi.")
    gl = ""
    if glossary:
        gl = "- Always use this glossary:\n" + "\n".join(f"  {k} => {v}" for k, v in glossary.items()) + "\n"
    sys = SYSTEM_PROMPT.format(src=LANG_NAMES.get(src, src), tgt=LANG_NAMES.get(tgt, tgt),
                               glossary=gl, extra=("- " + extra_prompt + "\n") if extra_prompt else "")
    numbered = {str(i + 1): t for i, t in enumerate(texts) if t.strip()}
    if not numbered:
        return ["" for _ in texts]
    user = json.dumps(numbered, ensure_ascii=False, indent=0)

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {"model": model, "temperature": temperature,
            "messages": [{"role": "system", "content": sys}, {"role": "user", "content": user}]}
    r = requests.post(base_url.rstrip("/") + "/chat/completions", json=body, headers=headers, timeout=180)
    if r.status_code != 200:
        raise TranslateError(f"LLM error {r.status_code}: {r.text[:300]}")
    content = r.json()["choices"][0]["message"]["content"]
    data = _parse_json(content)
    return [str(data.get(str(i + 1), "")) if texts[i].strip() else "" for i in range(len(texts))]


def _parse_json(content: str) -> dict:
    content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        raise TranslateError(f"Balasan LLM bukan JSON: {content[:200]}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise TranslateError(f"JSON LLM rusak: {e}")


def translate(texts: list[str], src: str, tgt: str, engine: str, settings: dict, glossary: dict | None = None):
    glossary = glossary or {}
    if engine == "google":
        return translate_google(texts, src, tgt, glossary)
    if engine == "deepl":
        return translate_deepl(texts, src, tgt, glossary, settings.get("deepl_key", ""))
    if engine == "llm":
        return translate_llm(texts, src, tgt, glossary,
                             settings.get("llm_base_url", ""), settings.get("llm_api_key", ""),
                             settings.get("llm_model", ""), settings.get("llm_extra_prompt", ""),
                             float(settings.get("llm_temperature", 0.3)))
    raise TranslateError(f"Engine terjemahan tidak dikenal: {engine}")
