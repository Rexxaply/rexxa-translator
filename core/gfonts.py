"""Google Fonts sebagai cadangan pencarian font (tanpa API key).

- Katalog   : https://fonts.google.com/metadata/fonts (daftar keluarga, kategori, ketebalan),
              disimpan seminggu di folder data. Bila offline: daftar bawaan di bawah.
- Unduh TTF : CSS API (fonts.googleapis.com/css2) dengan user-agent lama -> tautan .ttf di
              fonts.gstatic.com. Cadangan: repo GitHub google/fonts.
- File      : %APPDATA%/RexxaTranslator/gfonts/  (dipakai ulang, tidak diunduh dua kali).
Semua font Google Fonts berlisensi terbuka (OFL / Apache), boleh dipakai untuk hasil terjemahan.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

from . import paths

UA_TTF = "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)"   # CSS API memberi tautan .ttf
TIMEOUT = 15

# keluarga yang cocok untuk lettering komik / SFX / judul (dipakai bila katalog tidak tersedia,
# dan diutamakan saat mencocokkan)
BRUSH = ["Bangers", "Permanent Marker", "Rock Salt", "Caveat Brush", "Sedgwick Ave Display", "Knewave",
         "Rubik Wet Paint", "Rubik Dirt", "Rubik Spray Paint", "Creepster", "Nosifer", "Butcherman",
         "Eater", "Metal Mania", "New Rocker", "Frijole", "Shojumaru", "Fugaz One", "Racing Sans One",
         "Luckiest Guy", "Titan One", "Lilita One", "Bowlby One SC", "Black Ops One", "Rampart One",
         "Dela Gothic One", "Rubik Glitch", "Finger Paint", "Gochi Hand", "Kalam"]
COMIC = ["Comic Neue", "Bangers", "Patrick Hand", "Patrick Hand SC", "Gaegu",
         "Indie Flower", "Architects Daughter", "Short Stack", "Schoolbell", "Gloria Hallelujah",
         "Mansalva", "Kalam", "Itim", "Mali", "Sniglet"]
SANS_BOLD = ["Anton", "Bebas Neue", "Oswald", "Archivo Black", "Roboto Condensed", "Barlow Condensed",
             "Fjalla One", "Russo One", "Passion One", "Alfa Slab One", "Rubik", "Montserrat", "Poppins",
             "Inter", "Nunito", "Bungee", "Teko", "Saira Condensed", "Big Shoulders Display", "Black Han Sans",
             "Do Hyeon", "Zen Dots", "Exo 2", "Kanit", "Chakra Petch"]
FALLBACK = sorted(set(BRUSH + COMIC + SANS_BOLD))


def cache_dir() -> Path:
    d = paths.data_dir() / "gfonts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def downloaded() -> list[str]:
    d = paths.data_dir() / "gfonts"
    return sorted(str(p) for p in d.glob("*.ttf")) if d.exists() else []


# ---------------------------------------------------------------- katalog

def catalog(force: bool = False) -> list[dict]:
    """[{family, category, weights:[...], italic:bool, popularity}] -- kosong -> daftar bawaan."""
    f = paths.data_dir() / "gfonts_catalog.json"
    if not force and f.exists() and time.time() - f.stat().st_mtime < 7 * 86400:
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    try:
        r = requests.get("https://fonts.google.com/metadata/fonts", timeout=TIMEOUT)
        r.raise_for_status()
        txt = r.text
        data = json.loads(txt[txt.index("{"):])
        out = []
        for fam in data.get("familyMetadataList", []):
            keys = list((fam.get("fonts") or {}).keys())
            weights = sorted({int(re.sub(r"\D", "", k) or 400) for k in keys})
            out.append({"family": fam.get("family", ""), "category": fam.get("category", ""),
                        "weights": weights or [400], "italic": any(k.endswith("i") for k in keys),
                        "popularity": fam.get("popularity", 9999),
                        "subsets": fam.get("subsets", [])})
        out = [o for o in out if o["family"]]
        if out:
            try:
                f.write_text(json.dumps(out), encoding="utf-8")
            except Exception:
                pass
            return out
    except Exception:
        pass
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return [{"family": n, "category": "Display", "weights": [400, 700], "italic": False,
             "popularity": i, "subsets": ["latin"]} for i, n in enumerate(FALLBACK)]


def search(query: str, limit: int = 60) -> list[dict]:
    q = (query or "").strip().lower()
    cat = catalog()
    cat = [c for c in cat if "latin" in (c.get("subsets") or ["latin"])]
    if q:
        cat = [c for c in cat if q in c["family"].lower() or q == c.get("category", "").lower()]
    cat.sort(key=lambda c: (not c["family"].lower().startswith(q) if q else False, c.get("popularity", 9999)))
    return cat[:limit]


# ---------------------------------------------------------------- unduh

def _slug(family: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", family)


def _nearest(weights, want):
    return min(weights or [400], key=lambda w: abs(w - want))


def download(family: str, weight: int = 400, weights: list | None = None) -> str | None:
    """Unduh satu ketebalan font (TTF). Mengembalikan path, atau None bila gagal."""
    w = _nearest(weights, weight) if weights else weight
    dest = cache_dir() / f"{_slug(family)}-{w}.ttf"
    if dest.exists() and dest.stat().st_size > 1000:
        return str(dest)
    fam_q = family.replace(" ", "+")
    urls = []
    for q in (f"{fam_q}:wght@{w}", fam_q):
        try:
            r = requests.get(f"https://fonts.googleapis.com/css2?family={q}",
                             headers={"User-Agent": UA_TTF}, timeout=TIMEOUT)
            if r.ok:
                urls = re.findall(r"url\((https://[^)]+?\.ttf)\)", r.text)
                if urls:
                    break
        except Exception:
            pass
    if not urls:
        urls = _github_urls(family, w)
    for u in urls[:2]:
        try:
            r = requests.get(u, timeout=TIMEOUT * 2)
            if r.ok and len(r.content) > 1000:
                dest.write_bytes(r.content)
                return str(dest)
        except Exception:
            pass
    return None


def _github_urls(family: str, weight: int) -> list[str]:
    slug = re.sub(r"[^a-z0-9]", "", family.lower())
    for lic in ("ofl", "apache", "ufl"):
        try:
            r = requests.get(f"https://api.github.com/repos/google/fonts/contents/{lic}/{slug}", timeout=TIMEOUT)
            if not r.ok:
                continue
            files = [f for f in r.json() if f.get("name", "").lower().endswith(".ttf")]
            if not files:
                continue
            want = {400: "regular", 700: "bold", 900: "black", 800: "extrabold", 600: "semibold"}.get(weight, "")
            files.sort(key=lambda f: (("italic" in f["name"].lower()),
                                      not (want and want in f["name"].lower()), len(f["name"])))
            return [f["download_url"] for f in files if f.get("download_url")]
        except Exception:
            continue
    return []


# ---------------------------------------------------------------- kandidat untuk pencocokan

def candidates(src: dict, limit: int = 12) -> list[tuple[str, int, list]]:
    """Keluarga Google Fonts yang patut dicoba untuk ciri huruf src: [(family, weight, weights)]."""
    cat = {c["family"]: c for c in catalog()}
    rough = src.get("rough", 0) > 0.4
    heavy = src.get("stroke", 0) > 0.24
    names = (BRUSH + COMIC) if rough else (COMIC + SANS_BOLD if not heavy else SANS_BOLD + BRUSH[:10])
    # tambah keluarga populer dari kategori yang sesuai
    want_cat = ("Display", "Handwriting") if rough else ("Sans Serif", "Display")
    extra = sorted((c for c in cat.values() if c.get("category") in want_cat
                    and "latin" in (c.get("subsets") or ["latin"])),
                   key=lambda c: c.get("popularity", 9999))
    seen, out = set(), []
    for n in names + [c["family"] for c in extra]:
        if n in seen:
            continue
        seen.add(n)
        c = cat.get(n)
        weights = c["weights"] if c else [400, 700]
        out.append((n, 900 if heavy else 700, weights))
        if len(out) >= limit:
            break
    return out
