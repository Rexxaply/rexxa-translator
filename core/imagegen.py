"""AI pembuat gambar (endpoint kompatibel OpenAI: /v1/images/generations & /v1/images/edits).

Dipakai Kotak judul: logo judul asli dikirim sebagai referensi, AI menulis ulang judulnya
dalam bahasa tujuan dengan gaya yang sama (kuas, warna, cipratan, cahaya …).
Bisa dipakai dengan OpenAI langsung atau router yang meniru API OpenAI (mis. ClassAI:
Nano Banana, GPT Image, Seedream, FLUX dengan satu key).
"""
from __future__ import annotations

import base64
import io

import numpy as np
import requests
from PIL import Image

PRESETS = {   # nama: (base URL, model bawaan)
    "ClassAI router": ("https://router.classai.id/v1", "nano-banana-2"),
    "OpenAI": ("https://api.openai.com/v1", "gpt-image-1"),
}


class ImageGenError(Exception):
    pass


def title_prompt(title: str, hint: str = "", has_ref: bool = True) -> str:
    t = title.strip()
    base = (f'Recreate this comic series title logo with the new title text: "{t}". '
            if has_ref else f'Design a comic / manhwa series title logo with the text: "{t}". ')
    base += ("Keep the same art style as the reference: lettering style (brush strokes, calligraphy, "
             "thickness, slant), colors and color accents, outline, glow, paint splatter, speed streaks, "
             "texture and overall composition. " if has_ref else
             "Bold dynamic brush lettering, strong outline, vivid colors, splatter and glow effects. ")
    base += (f'Spell every word exactly: "{t}" (keep the language as written, do not translate, '
             "no extra words, no subtitle, no credits, no watermark). Centered logo on a plain pure white "
             "background, nothing else in the image.")
    if hint.strip():
        base += " Extra style notes: " + hint.strip()
    return base


def _headers(key: str) -> dict:
    h = {"User-Agent": "RexxaTranslator"}
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def _parse(resp) -> list[bytes]:
    if resp.status_code != 200:
        msg = resp.text[:400]
        try:
            j = resp.json()
            msg = (j.get("error") or {}).get("message") or j.get("message") or msg
        except ValueError:
            pass
        raise ImageGenError(f"AI gambar error {resp.status_code}: {msg}")
    try:
        data = resp.json().get("data") or []
    except ValueError:
        raise ImageGenError("Balasan AI gambar bukan JSON.")
    out = []
    for d in data:
        if d.get("b64_json"):
            out.append(base64.b64decode(d["b64_json"]))
        elif d.get("url"):
            r = requests.get(d["url"], timeout=120)
            r.raise_for_status()
            out.append(r.content)
    if not out:
        raise ImageGenError("AI gambar tidak mengembalikan gambar.")
    return out


def edit(settings: dict, ref_png: bytes, prompt: str, n: int = 2, timeout: int = 300) -> list[bytes]:
    """Edit / tulis ulang gambar referensi. Mengembalikan daftar gambar (bytes)."""
    base = (settings.get("img_base_url") or "").rstrip("/")
    if not base:
        raise ImageGenError("Base URL AI gambar belum diisi.")
    model = settings.get("img_model") or ""
    data = {"model": model, "prompt": prompt, "n": str(max(1, min(4, n)))}
    files = {"image": ("logo.png", ref_png, "image/png")}
    r = requests.post(base + "/images/edits", data=data, files=files,
                      headers=_headers(settings.get("img_api_key", "")), timeout=timeout)
    if r.status_code in (400, 422) and "n" in r.text.lower() and n > 1:
        # sebagian model hanya menerima 1 gambar per permintaan -> ulangi satu per satu
        out = []
        for _ in range(n):
            out += edit(settings, ref_png, prompt, 1, timeout)
        return out
    return _parse(r)


def generate(settings: dict, prompt: str, n: int = 2, timeout: int = 300) -> list[bytes]:
    base = (settings.get("img_base_url") or "").rstrip("/")
    if not base:
        raise ImageGenError("Base URL AI gambar belum diisi.")
    body = {"model": settings.get("img_model") or "", "prompt": prompt, "n": max(1, min(4, n))}
    r = requests.post(base + "/images/generations", json=body,
                      headers=_headers(settings.get("img_api_key", "")), timeout=timeout)
    return _parse(r)


def to_png(img_bgr_crop: np.ndarray, max_side: int = 1024) -> bytes:
    rgb = Image.fromarray(np.ascontiguousarray(img_bgr_crop[..., ::-1]))
    rgb.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    rgb.save(buf, "PNG")
    return buf.getvalue()


def remove_plain_bg(data: bytes, tol: float = 26.0) -> Image.Image:
    """Latar polos (putih / satu warna) -> transparan, tepi halus. Dipotong rapat ke logonya."""
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    a = np.asarray(im).astype(np.float32)
    rgb = a[..., :3]
    H, W = rgb.shape[:2]
    b = max(2, min(H, W) // 50)
    border = np.concatenate([rgb[:b].reshape(-1, 3), rgb[-b:].reshape(-1, 3),
                             rgb[:, :b].reshape(-1, 3), rgb[:, -b:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    if np.median(np.abs(border - bg).max(axis=1)) > 18:      # latar tidak polos -> biarkan
        return im
    import cv2
    dist = np.abs(rgb - bg).max(axis=2)
    # hanya latar yang tersambung ke tepi gambar (isi huruf putih di dalam garis tepi tetap utuh)
    near = (dist < tol).astype(np.uint8)
    n, lab = cv2.connectedComponents(near, connectivity=4)
    edge_labels = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    outer = np.isin(lab, edge_labels[edge_labels > 0])
    band = cv2.dilate(outer.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    soft = np.clip((dist - tol * 0.5) / tol, 0, 1)
    alpha = np.where(outer, 0.0, np.where(band, np.maximum(soft, 0.35), 1.0)).astype(np.float32)
    # warna tepi: buang campuran latar (un-premultiply sederhana)
    al = np.maximum(alpha, 1e-3)[..., None]
    fg = np.clip((rgb - bg * (1 - al)) / al, 0, 255)
    out = np.dstack([np.where(alpha[..., None] > 0, fg, rgb), alpha * 255]).astype(np.uint8)
    res = Image.fromarray(out, "RGBA")
    box = res.getbbox()
    return res.crop(box) if box else res
