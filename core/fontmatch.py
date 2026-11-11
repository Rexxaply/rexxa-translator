"""Cocokkan font: cari font yang bentuk hurufnya paling mirip dengan teks asli
(dipakai untuk teks spesial / SFX).

Urutan pencarian: font aplikasi & font yang diinstal di Rexxa -> font perangkat (Windows/macOS/
Linux). Yang dipilih adalah yang paling mirip; font aplikasi sedikit diutamakan bila hampir sama.

Ciri yang dibandingkan (semua relatif terhadap tinggi huruf, jadi tidak tergantung ukuran):
- tebal goresan        (huruf kuas tebal vs tipis)
- kepadatan tinta      (huruf "penuh" vs berongga)
- kekasaran tepi       (kuas/kasar vs rapi)
- kemiringan           (italic)
- lebar huruf          (condensed vs lebar)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import paths

SAMPLE = "AEGHKMNRSWBOD"
_SKIP = ("symbol", "wingding", "webding", "marlett", "emoji", "mdl2", "holomdl", "fluent", "icons",
         "dingbat", "bookshelf", "extra", "ornament", "math", "braille", "music", "segmdl", "opensymbol",
         "cjk", "barcode")
# ciri: (bobot, skala beda yang dianggap "jauh")
_WEIGHTS = {"stroke": (3.0, 0.05), "fill": (1.5, 0.12), "rough": (1.5, 0.25),
            "slant": (1.0, 0.15), "aspect": (1.0, 0.25)}
_cache: dict = {}
_VER = 5          # naikkan bila cara menghitung ciri berubah (cache lama diabaikan)


# ---------------------------------------------------------------- daftar font perangkat

def system_font_dirs() -> list[Path]:
    home = Path.home()
    if sys.platform.startswith("win"):
        win = Path(os.environ.get("WINDIR", r"C:\Windows"))
        dirs = [win / "Fonts", Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local")) / "Microsoft/Windows/Fonts"]
    elif sys.platform == "darwin":
        dirs = [Path("/System/Library/Fonts"), Path("/Library/Fonts"), home / "Library/Fonts"]
    else:
        dirs = [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), home / ".fonts", home / ".local/share/fonts"]
    return [d for d in dirs if d.exists()]


def system_fonts() -> list[str]:
    out = []
    for d in system_font_dirs():
        for ext in ("*.ttf", "*.otf", "*.ttc", "*.TTF", "*.OTF", "*.TTC"):
            out += [str(p) for p in d.rglob(ext)]
    return sorted(set(out))


def _usable(path: str) -> bool:
    n = Path(path).stem.lower()
    return not any(k in n for k in _SKIP)


# ---------------------------------------------------------------- ciri bentuk huruf

def _features(ink: np.ndarray, min_h: float) -> dict | None:
    """ink: gambar biner (1 = tinta). Ciri rata-rata dari komponen setinggi huruf."""
    ink = (ink > 0).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    vals = {k: [] for k in _WEIGHTS}
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if h < min_h or a < 20:
            continue
        comp = (lbl[y:y + h, x:x + w] == i).astype(np.uint8)
        cnts, _ = cv2.findContours(comp, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        per = sum(cv2.arcLength(c, True) for c in cnts)
        if per <= 0:
            continue
        # tepi halus = kontur setelah diburamkan -> perbandingan panjang tepi = kekasaran
        sig = max(1.0, h * 0.04)
        sm = (cv2.GaussianBlur(comp.astype(np.float32), (0, 0), sig) > 0.5).astype(np.uint8)
        cs, _ = cv2.findContours(sm, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        per_s = sum(cv2.arcLength(c, True) for c in cs) or per
        m = cv2.moments(comp, binaryImage=True)
        # tebal goresan: rata-rata jarak ke tepi untuk goresan setebal t kira-kira t/4
        padded = cv2.copyMakeBorder(comp, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
        dist = cv2.distanceTransform(padded, cv2.DIST_L2, 5)
        vals["stroke"].append(4.0 * float(dist[padded > 0].mean()) / h)
        vals["fill"].append(a / float(w * h))
        vals["rough"].append(float(np.log(per / per_s)) * 4.0)
        vals["slant"].append(-m["mu11"] / m["mu02"] if m["mu02"] else 0.0)
        vals["aspect"].append(w / float(h))
    if len(vals["stroke"]) < 2:
        return None
    return {k: float(np.median(v)) for k, v in vals.items()}


def source_features(img: np.ndarray, rect, src_h: int) -> dict | None:
    """Ciri huruf teks asli di dalam rect [x, y, w, h]."""
    x, y, w, h = (int(v) for v in rect)
    crop = img[max(0, y):y + h, max(0, x):x + w]
    if crop.size == 0:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if np.median(gray) < 100:          # huruf terang/berwarna di latar gelap (logo judul)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV).astype(np.float32)
        colour = (hsv[..., 1] * hsv[..., 2] / 255.0).astype(np.uint8)   # warna pekat, bukan hitam
        gray = 255 - cv2.max(gray, colour)
    t, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ink = gray < min(t, 140)
    sh = src_h or h
    # goresan kuas sering bergaris-garis putih di dalamnya: tutup celah kecil dulu
    k = max(3, int(sh * 0.05)) | 1
    ink = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((k, k), np.uint8)) > 0
    # buang komponen terlalu besar (garis balon, rambut) sebelum dihitung
    n, lbl, st, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    for i in range(1, n):
        if st[i][3] <= sh * 1.6 and st[i][2] <= sh * 2.6:
            keep[i] = True
    keep[0] = False
    return _features(keep[lbl], sh * 0.5)


def font_features(path: str) -> dict | None:
    key = path
    if key in _cache:
        return _cache[key]
    feat = None
    try:
        f = ImageFont.truetype(path, 96)
        if not _has_latin(f):
            _cache[key] = None
            return None
        text = "  ".join(SAMPLE)
        l, t, r, b = f.getbbox(text)
        if r - l > 40 and b - t > 30:
            im = Image.new("L", (r - l + 40, b - t + 40), 0)
            ImageDraw.Draw(im).text((20 - l, 20 - t), text, font=f, fill=255)
            arr = np.array(im)
            # font tanpa huruf latin menggambar kotak kosong yang sama untuk semua huruf
            feat = _features(arr > 127, 40)
    except Exception:
        feat = None
    _cache[key] = feat
    return feat


def _has_latin(f) -> bool:
    """Font simbol / tanpa huruf latin menggambar kotak yang sama untuk setiap huruf."""
    seen = set()
    for ch in "ABOe":
        m = f.getmask(ch)
        if m.size[0] == 0 or m.size[1] == 0:
            return False
        seen.add((m.size, bytes(m)))
    return len(seen) == 4


def _load_disk_cache():
    p = paths.data_dir() / f"font_features_v{_VER}.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        for k, v in d.items():
            _cache.setdefault(k, v)
    except Exception:
        pass


def _save_disk_cache():
    p = paths.data_dir() / f"font_features_v{_VER}.json"
    try:
        p.write_text(json.dumps(_cache), encoding="utf-8")
    except Exception:
        pass


# font bergaya komik / kuas / poster: diutamakan untuk SFX yang tepinya kasar
_DISPLAY = ("wild", "badaboom", "komika", "bangers", "anime ace", "animeace", "impact", "ink free", "inkfree",
            "segoe print", "segoepr", "comic", "brush", "marker", "kristen", "showcard", "chiller", "jokerman",
            "bauhaus", "cooper black", "permanent", "creepster", "luckiest", "boogaloo", "bebas", "black", "heavy")
_SERIF = ("serif", "times", "georgia", "garamond", "caladea", "cambria", "book antiqua", "palatino", "century")

# font hiasan / judul / sambung yang TIDAK cocok untuk dialog & narasi (sulit dibaca, terlalu lebar,
# huruf kapital hias, dsb.). Nama file Windows (mis. GOUDYSTO.TTF = Goudy Stout) & nama keluarga.
_DECOR = ("goudysto", "goudystout", "alger", "broadw", "castelar", "castellar", "chiller", "jokerman",
          "oldengl", "oldenglish", "ravie", "snap", "showg", "showcard", "stencil", "latinwd", "widelatin",
          "playbill", "harngton", "harrington", "vivaldi", "curlz", "bauhs", "bauhaus", "itcblkad",
          "blackadder", "itcedscr", "edwardian", "engr", "engravers", "felixti", "felixtitling", "gigi",
          "kunstler", "magneto", "maturasc", "matura", "mistral", "niageng", "niagsol", "niagara",
          "parchm", "parchment", "poorich", "poorrichard", "rage", "vineritc", "viner", "vladimir",
          "infroman", "informalroman", "juice", "pristina", "papyrus", "colonna", "bodpstc", "bodonipost",
          "forte", "freescpt", "freestyle", "frscript", "frenchscript", "imprisha", "imprint", "onyx",
          "coprgt", "copperplate", "perti", "perpetuatitling", "agency", "hatten", "haettenschweiler",
          "elephnt", "elephant", "brlns", "tempsitc", "tempus", "harlowsi", "harlow", "palscri", "palace",
          "glecb", "gloucester", "scriptbl", "scriptmt", "brushsci", "brushscript", "lcallig",
          "lucidacalligraphy", "lhandw", "lucidahandwriting", "ocraext", "ocra", "mod20", "modernno",
          "segoesc", "segoescript", "gabriola", "bernhc", "bernard", "britanic", "britannic",
          "goudyst", "rosewood", "wingding", "webding", "holtwood", "monotypecorsiva", "mtcorsva",
          "kaushan", "pacifico", "lobster", "greatvibes", "allura", "dancingscript", "sacramento",
          "unifraktur", "fraktur", "blackletter", "cinzeldecorative", "monoton", "bungeeshade",
          "fasterone", "ewert", "codystar", "frijole", "nosifer", "eater", "creepster")


def is_decorative(path: str) -> bool:
    """Font hiasan yang tidak dipakai untuk dialog / narasi (tetap boleh untuk SFX / judul)."""
    k = "".join(ch for ch in Path(path).stem.lower() if ch.isalnum())
    return any(k.startswith(d) for d in _DECOR)


def _lower_ratio(path: str) -> float:
    """Tinggi huruf kecil 'x' dibanding 'X' (~1.0 = font kapital saja / huruf kecil = kapital)."""
    try:
        f = ImageFont.truetype(path, 64)
        lx = f.getbbox("x")
        ux = f.getbbox("X")
        return (lx[3] - lx[1]) / max(1, ux[3] - ux[1])
    except Exception:
        return 1.0


def distance(a: dict, b: dict) -> float:
    # setiap ciri dibatasi: satu ciri yang meleset jauh (mis. kekasaran tepi kuas yang tidak dimiliki
    # font mana pun) tidak boleh menentukan pilihan sendirian
    return float(sum(w * min(3.0, abs(a[k] - b[k]) / s) for k, (w, s) in _WEIGHTS.items()))


def _style_bias(path: str, src: dict) -> float:
    n = Path(path).stem.lower().replace("-", " ").replace("_", " ")
    bias = 0.0
    if src.get("rough", 0) > 0.4:             # huruf kuas / kasar (SFX)
        if any(k in n for k in _DISPLAY):
            bias -= 2.0
        if any(k in n for k in _SERIF) and "sans" not in n:
            bias += 2.0
    if any(k in n for k in ("mono", "code", "console", "courier")):
        bias += 1.0
    return bias


def candidates(include_system: bool = True) -> list[tuple[str, float]]:
    """(path, penalti): font aplikasi tanpa penalti, font perangkat sedikit penalti."""
    from .typeset import list_fonts
    out, seen = [], set()
    for p in list_fonts():
        if p not in seen and _usable(p):
            seen.add(p)
            out.append((p, 0.0))
    if include_system:
        for p in system_fonts():
            if p not in seen and _usable(p):
                seen.add(p)
                out.append((p, 0.15))
    try:   # font Google Fonts yang sudah pernah diunduh
        from .gfonts import downloaded
        for p in downloaded():
            if p not in seen:
                seen.add(p)
                out.append((p, 0.1))
    except Exception:
        pass
    return out


def _weight_bias(path: str) -> float:
    n = Path(path).stem.lower()
    if any(k in n for k in ("black", "heavy", "extrabold", "ultra", "bold", "impact", "poster")):
        return -1.5
    if any(k in n for k in ("light", "thin", "hairline", "mono", "code")):
        return 2.0
    return 0.0


GOOD_ENOUGH = 3.0      # skor di bawah ini = font lokal sudah cukup mirip, Google Fonts tidak dicari


def best_font(img: np.ndarray, rect, src_h: int, include_system: bool = True, top: int = 1,
              heavy: bool = False, online: bool = False, log=None, readable: bool = False,
              lowercase: bool = False):
    """Font paling mirip untuk teks di rect. Mengembalikan path (atau list (path, skor) bila top>1).
    heavy=True : utamakan font tebal (logo judul).
    online=True: bila font lokal kurang mirip, cari cadangan di Google Fonts (diunduh & disimpan)."""
    src = source_features(img, rect, src_h)
    if src is None:
        return None if top == 1 else []
    if not _cache:
        _load_disk_cache()
    n0 = len(_cache)

    def score(path, pen):
        if readable and is_decorative(path):
            return None                  # dialog / narasi: tanpa font hiasan
        f = font_features(path)
        if not f:
            return None
        if readable:
            # lebar huruf harus mirip (font sangat lebar / sempit membuat teks tidak muat & aneh)
            if src.get("aspect") and f.get("aspect") and \
                    not (0.68 <= f["aspect"] / max(1e-3, src["aspect"]) <= 1.45):
                return None
            if abs(f.get("slant", 0)) > 0.45:
                return None              # sangat miring (huruf sambung)
            if lowercase and _lower_ratio(path) > 0.9:
                return None              # teks asli huruf kecil: jangan font kapital saja
        return (distance(src, f) + pen + _style_bias(path, src)
                + (_weight_bias(path) if heavy else 0.0), path)

    scored = [r for r in (score(p, pen) for p, pen in candidates(include_system)) if r]
    scored.sort()
    if online and (not scored or scored[0][0] > GOOD_ENOUGH):
        try:
            from . import gfonts
            have = {p for _s, p in scored}
            for fam, wt, weights in gfonts.candidates(src):
                p = gfonts.download(fam, wt, weights)
                if p and p not in have:
                    have.add(p)
                    r = score(p, 0.1)
                    if r:
                        scored.append(r)
                        if log:
                            log(f"Google Fonts: {fam} ({r[0]:.1f})")
            scored.sort()
        except Exception as e:
            if log:
                log(f"Google Fonts tidak dapat dihubungi: {e}")
    if len(_cache) != n0:
        _save_disk_cache()
    if top == 1:
        if not scored:
            return None
        best = scored[0][1]
        try:   # font Google yang terpilih langsung dipasang -> muncul di daftar font aplikasi
            from .gfonts import cache_dir
            if Path(best).parent == cache_dir():
                from .typeset import install_font
                best = install_font(best)
        except Exception:
            pass
        return best
    return [(p, s) for s, p in scored[:top]]
