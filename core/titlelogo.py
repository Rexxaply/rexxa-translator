"""Judul seri / logo (mis. "AFTER TEN MILLENNIA IN HELL") -> logo terjemahan bergaya mirip.

1. find_title     : cari logo = kumpulan huruf berwarna/terang terbesar di latar gelap (atau sebaliknya).
2. clean_title    : hapus logo asli, latar dibuat ulang.
3. render_title   : susun judul terjemahan (kata penting besar, kata sambung kecil, baris zig-zag),
                    huruf diisi TEKSTUR dari logo asli, tepi dibuat kasar seperti kuas bila aslinya kasar,
                    lalu diberi bayangan / cahaya dan kemiringan seperti aslinya.
"""
from __future__ import annotations

import re

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SMALL_WORDS = {"yang", "di", "ke", "dari", "dan", "setelah", "sebelum", "untuk", "dengan", "para", "sang", "si",
               "the", "in", "of", "a", "an", "to", "for", "with", "and", "on", "at", "after", "is", "my", "no", "wa"}


# ---------------------------------------------------------------- 1. temukan logo

def title_mask(img: np.ndarray) -> np.ndarray:
    """Piksel 'huruf logo': berwarna (jenuh) atau sangat kontras dengan latar halaman."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bg = float(np.median(gray))
    colored = (hsv[..., 1] > 80) & (hsv[..., 2] > 60)
    if bg < 80:      # latar gelap: huruf terang/berwarna
        ink = colored | (gray > bg + 90)
    else:            # latar terang: huruf gelap/berwarna
        ink = colored | (gray < bg - 90)
    return ink.astype(np.uint8)


def find_title(img: np.ndarray):
    """Kotak logo [x, y, w, h] + mask hurufnya, atau (None, None)."""
    H, W = img.shape[:2]
    ink = title_mask(img)
    k = max(9, int(W * 0.06)) | 1           # satukan huruf-huruf logo jadi satu gumpalan
    blob = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(blob, connectivity=8)
    best, score = 0, 0.0
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if w < W * 0.3 or h < W * 0.06:      # logo cukup lebar & tinggi
            continue
        if y <= 2 or y + h >= H - 2:          # bilah status / tepi
            continue
        inside = ink[y:y + h, x:x + w].sum()
        s = inside * (1.0 if w < W * 0.98 else 0.5)
        if s > score:
            best, score = i, s
    if not best:
        return None, None
    x, y, w, h, _ = st[best]
    m = np.zeros_like(ink)
    m[y:y + h, x:x + w] = ink[y:y + h, x:x + w] & (lbl[y:y + h, x:x + w] == best)
    return [int(x), int(y), int(w), int(h)], m


# ---------------------------------------------------------------- ciri gaya logo asli

def style_of(img, rect, mask) -> dict:
    x, y, w, h = rect
    m = mask[y:y + h, x:x + w] > 0
    crop = img[y:y + h, x:x + w]
    px = crop[m]
    color = np.median(px, axis=0) if len(px) else np.array([40, 40, 220])
    # kekasaran tepi: panjang kontur dibanding kontur yang dihaluskan
    mm = m.astype(np.uint8)
    cnts, _ = cv2.findContours(mm, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    per = sum(cv2.arcLength(c, True) for c in cnts)
    sm = (cv2.GaussianBlur(mm.astype(np.float32), (0, 0), max(1.0, h * 0.01)) > 0.5).astype(np.uint8)
    cs, _ = cv2.findContours(sm, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    per_s = sum(cv2.arcLength(c, True) for c in cs) or per or 1
    rough = float(per / per_s)
    if rough > 1.5:        # huruf bergradasi/bertekstur pecah-pecah di mask -> bukan tepi kuas
        rough = 1.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    light_bg = float(np.median(gray)) > 140
    # kemiringan huruf (shear) dari momen
    mo = cv2.moments(mm, binaryImage=True)
    slant = float(-mo["mu11"] / mo["mu02"]) if mo["mu02"] else 0.0
    return {"color": color, "rough": rough, "slant": slant, "light_bg": light_bg}


def _fill_stroke(px: np.ndarray):
    """Pisahkan warna isi huruf & warna garis tepi (2 kelompok warna). (isi_mask, warna_tepi | None)."""
    if len(px) < 50:
        return np.ones(len(px), bool), None
    data = px.astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _c, lab, cen = cv2.kmeans(data, 2, None, crit, 2, cv2.KMEANS_PP_CENTERS)
    lab = lab.ravel()
    n1 = int(lab.sum())
    big = 1 if n1 >= len(lab) - n1 else 0
    small_n = len(lab) - n1 if big == 1 else n1
    if small_n < 0.12 * len(lab) or np.linalg.norm(cen[0] - cen[1]) < 60:
        return np.ones(len(px), bool), None
    return lab == big, cen[1 - big]


def texture_of(img, rect, mask) -> np.ndarray:
    """Isi huruf baru: gradasi warna isi logo asli dari atas ke bawah (tanpa menyalin huruf aslinya,
    jadi tidak ada 'hantu' huruf lama / kotak gelap di dalam huruf baru)."""
    x, y, w, h = rect
    crop = img[y:y + h, x:x + w]
    m = mask[y:y + h, x:x + w] > 0
    core = cv2.erode(m.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    if not core.any():
        return np.full((h, w, 3), 200, np.uint8)
    ys, xs = np.nonzero(core)
    px = crop[ys, xs]
    fill, _stroke = _fill_stroke(px)
    ys, px = ys[fill], px[fill]
    rows = np.full((h, 3), np.nan, np.float32)
    for r in np.unique(ys):
        rows[r] = np.median(px[ys == r], axis=0)
    ok = ~np.isnan(rows[:, 0])
    idx = np.arange(h)
    for c in range(3):
        rows[:, c] = np.interp(idx, idx[ok], rows[ok, c])
    rows = cv2.GaussianBlur(rows.reshape(h, 1, 3), (1, 0), sigmaX=0.1, sigmaY=max(1.0, h * 0.04)).reshape(h, 3)
    return np.repeat(rows[:, None, :], w, axis=1).clip(0, 255).astype(np.uint8)


def stroke_of(img, rect, mask):
    x, y, w, h = rect
    m = cv2.erode((mask[y:y + h, x:x + w] > 0).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    px = img[y:y + h, x:x + w][m]
    return _fill_stroke(px)[1]


# ---------------------------------------------------------------- 2. hapus logo asli

def clean_title(img, rect, mask) -> np.ndarray:
    # semua yang berbeda dari latar di area logo (termasuk bagian logo yang redup / cahaya)
    H, W = img.shape[:2]
    x, y, w, h = rect
    e = int(max(w, h) * 0.04)
    x0, y0, x1, y1 = max(0, x - e), max(0, y - e), min(W, x + w + e), min(H, y + h + e)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    bg = float(np.median(g))
    loose = np.zeros_like(mask)
    sub = (np.abs(g[y0:y1, x0:x1].astype(int) - bg) > 22) | ((hsv[y0:y1, x0:x1, 1] > 50) & (hsv[y0:y1, x0:x1, 2] > 40))
    loose[y0:y1, x0:x1] = sub
    near = cv2.dilate(mask, np.ones((max(5, int(h * 0.08)) | 1,) * 2, np.uint8))
    m = cv2.dilate(((mask > 0) | ((loose > 0) & (near > 0))).astype(np.uint8) * 255,
                   np.ones((7, 7), np.uint8), iterations=2)
    out = img.copy()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ring = cv2.dilate(m, np.ones((15, 15), np.uint8)) & ~m
    vals = img[ring > 0]
    if len(vals) and np.median(np.abs(gray[ring > 0].astype(int) - np.median(gray[ring > 0]))) < 6:
        out[m > 0] = np.median(vals, axis=0).astype(np.uint8)       # latar polos (mis. hitam)
        return out
    try:
        from .inpaint import _inpaint_lama, lama_available
        if lama_available():
            return _inpaint_lama(out, m)
    except Exception:
        pass
    return cv2.inpaint(out, m, 7, cv2.INPAINT_TELEA)


# ---------------------------------------------------------------- 3. susun & gambar judul baru

def plan_lines(title: str) -> list[list[tuple[str, bool]]]:
    """Kata penting besar, kata sambung kecil; kata sambung menempel ke kata besar berikutnya,
    angka menempel dengan satuan sesudahnya ("10.000 TAHUN")."""
    words = [w for w in re.split(r"\s+", title.strip()) if w]
    lines, cur = [], []
    i = 0
    while i < len(words):
        w = words[i]
        small = w.lower().strip(",.!?") in SMALL_WORDS and len(words) > 2
        cur.append((w, small))
        if not small:
            if re.match(r"^[\d.,]+$", w) and i + 1 < len(words):      # angka + satuan satu baris
                cur.append((words[i + 1], False))
                i += 1
            lines.append(cur)
            cur = []
        i += 1
    if cur:
        if lines:
            lines[-1] += cur
        else:
            lines.append(cur)
    return lines


def _regroup(lines, aspect: float, width_of, base: float):
    """Gabungkan baris (1 kata penting per baris) supaya bentuk judul mendekati bentuk kotaknya:
    kotak lebar -> 1-2 baris, kotak tinggi -> banyak baris."""
    if len(lines) <= 1:
        return lines
    best, best_err = lines, 9e9
    n_all = len(lines)
    for n in range(1, n_all + 1):
        # bagi rata berurutan
        groups, k = [], 0
        for g in range(n):
            take = (n_all - k) // (n - g)
            groups.append([wd for ln in lines[k:k + take] for wd in ln])
            k += take
        wid = max(width_of(gp) for gp in groups)
        asp = wid / (n * base * 0.95)
        err = abs(np.log(asp / max(0.05, aspect)))
        if err < best_err - 1e-6:
            best, best_err = groups, err
    return best


def _brush(alpha: np.ndarray, size: int, rough: float, seed: int = 7) -> np.ndarray:
    """Tepi kasar & goresan kuas: geser tepi huruf dengan derau halus + gores mendatar."""
    if rough < 1.08:
        return alpha
    rng = np.random.default_rng(seed)
    H, W = alpha.shape
    amp = size * min(0.07, 0.025 + (rough - 1.0) * 0.15)
    def field(sig):
        f = cv2.GaussianBlur(rng.standard_normal((H, W)).astype(np.float32), (0, 0), sig)
        return f / (np.abs(f).max() + 1e-6)
    dx = field(size * 0.05) * amp
    dy = field(size * 0.05) * amp * 0.6
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    out = cv2.remap(alpha, gx + dx, gy + dy, cv2.INTER_LINEAR)
    # gores kuas: celah tipis memanjang (derau yang diburamkan jauh lebih kuat ke arah mendatar)
    n = rng.standard_normal((H, W)).astype(np.float32)
    streak = cv2.GaussianBlur(n, (0, 0), sigmaX=size * 0.35, sigmaY=max(1.0, size * 0.012))
    streak = streak / (np.abs(streak).max() + 1e-6)
    cut = (streak > 0.42).astype(np.float32)
    out = out * (1.0 - 0.9 * cut)
    # serpihan kuas: tepi digerus derau halus (bintik-bintik di pinggir huruf)
    fine = cv2.GaussianBlur(rng.standard_normal((H, W)).astype(np.float32), (0, 0), max(1.0, size * 0.012))
    fine = fine / (np.abs(fine).max() + 1e-6)
    edge = (out > 20) & (cv2.erode(out, np.ones((5, 5), np.uint8)) < 200)
    out[edge & (fine > 0.25)] = 0
    return np.clip(out, 0, 255).astype(np.uint8)


def mask_in_rect(img, rect) -> np.ndarray:
    """Mask huruf logo di dalam kotak (kotak bisa digeser/diubah manual di editor)."""
    H, W = img.shape[:2]
    x, y, w, h = (int(v) for v in rect)
    full = title_mask(img)
    m = np.zeros_like(full)
    m[max(0, y):y + h, max(0, x):x + w] = full[max(0, y):y + h, max(0, x):x + w]
    return m


def render_title(img, title: str, rect, mask, font_path: str, upper: bool = True, onto=None) -> np.ndarray:
    """img = halaman asli (sumber gaya & tekstur), onto = gambar tujuan (mis. hasil yang sudah
    dibersihkan & diketik); default = img."""
    x, y, w, h = (int(v) for v in rect)
    rect = [x, y, w, h]
    st = style_of(img, rect, mask)
    tex = texture_of(img, rect, mask)
    text = title.upper() if upper else title
    lines = plan_lines(text)

    # ukuran: tiap baris dibuat selebar ~kotak asli, kata kecil 45%
    base = 200
    f_big = ImageFont.truetype(font_path, base)
    f_small = ImageFont.truetype(font_path, int(base * 0.45))
    meas = ImageDraw.Draw(Image.new("L", (8, 8)))

    def word_w(word, small):
        f = f_small if small else f_big
        return meas.textlength(word, font=f)

    gap = base * 0.18
    lines = _regroup(lines, w / max(1, h), lambda ln: sum(word_w(wd, sm) for wd, sm in ln) + gap * (len(ln) - 1),
                     base)
    rows = []
    for ln in lines:
        ww = sum(word_w(wd, sm) for wd, sm in ln) + gap * (len(ln) - 1)
        rows.append((ln, ww))
    widest = max(r[1] for r in rows)
    # baris pendek diperbesar sedikit (seperti logo: tiap baris hampir sama lebar)
    scales = [min(1.35, widest / max(1.0, r[1]) * 0.85 + 0.15) for r in rows]
    heights = [base * s * 1.0 for s in scales]
    total_h = sum(heights) * 0.92
    canvas_w = int(widest * 1.25 + base)
    canvas_h = int(total_h + base * 1.2)
    alpha = Image.new("L", (canvas_w, canvas_h), 0)
    d = ImageDraw.Draw(alpha)
    cy = base * 0.6
    for k, ((ln, ww), sc, hh) in enumerate(zip(rows, scales, heights)):
        fb = ImageFont.truetype(font_path, max(8, int(base * sc)))
        fs = ImageFont.truetype(font_path, max(8, int(base * sc * 0.45)))
        lw = sum(d.textlength(wd, font=(fs if sm else fb)) for wd, sm in ln) + gap * sc * (len(ln) - 1)
        stagger = (-1) ** k * widest * 0.05 if len(rows) > 1 else 0
        cx = (canvas_w - lw) / 2 + stagger
        for wd, sm in ln:
            f = fs if sm else fb
            # kata kecil di bagian atas baris (seperti "yang" pada logo)
            yy = cy + (hh * 0.08 if sm else 0)
            l0, t0, _, _ = d.textbbox((0, 0), wd, font=f)
            d.text((cx - l0, yy - t0), wd, font=f, fill=255)
            cx += d.textlength(wd, font=f) + gap * sc
        cy += hh * 0.92
    a = np.array(alpha)
    ys, xs = np.nonzero(a > 10)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    # miring seperti aslinya (huruf condong ke kanan)
    sh = 0.18 if st["slant"] > 0.05 or st["rough"] > 1.15 else 0.0
    if sh:
        H0, W0 = a.shape
        pad = int(H0 * sh) + 2
        a = cv2.copyMakeBorder(a, 0, 0, pad, pad, cv2.BORDER_CONSTANT, value=0)
        M = np.float32([[1, -sh, sh * H0 / 2], [0, 1, 0]])
        a = cv2.warpAffine(a, M, (a.shape[1], H0))
    # muat ke kotak asli (tanpa mengubah perbandingan)
    s = min(w * 1.02 / a.shape[1], h * 1.05 / a.shape[0])
    a = cv2.resize(a, (max(1, int(a.shape[1] * s)), max(1, int(a.shape[0] * s))), interpolation=cv2.INTER_AREA)
    a = _brush(a, int(base * s), st["rough"])
    ah, aw = a.shape
    ox, oy = x + (w - aw) // 2, y + (h - ah) // 2

    out = clean_title(img if onto is None else onto, rect, mask)
    H, W = out.shape[:2]
    X0, Y0, X1, Y1 = max(0, ox), max(0, oy), min(W, ox + aw), min(H, oy + ah)
    if X1 <= X0 or Y1 <= Y0:
        return out
    A = a[Y0 - oy:Y1 - oy, X0 - ox:X1 - ox].astype(np.float32) / 255.0
    region = out[Y0:Y1, X0:X1].astype(np.float32)
    sy, sx = int(ah * 0.012) + 1, int(ah * 0.008) + 1          # bayangan geser (tanpa membungkus tepi)
    shadow = np.zeros_like(A)
    shadow[sy:, sx:] = A[:A.shape[0] - sy, :A.shape[1] - sx]
    if st.get("light_bg"):
        # latar terang: garis tepi gelap (warna logo yang digelapkan) supaya huruf tetap terbaca
        r = max(2, int(ah * 0.012))
        ring = cv2.dilate((A > 0.3).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2))
        ring = cv2.GaussianBlur(ring.astype(np.float32), (0, 0), 0.8)[..., None]
        ocol = np.array(st["color"], np.float32) * 0.35
        region = region * (1 - ring) + ocol * ring
        region = region * (1 - 0.25 * shadow[..., None])
    else:
        # latar gelap: cahaya warna logo + bayangan
        glow = cv2.GaussianBlur(A, (0, 0), max(2.0, ah * 0.02))[..., None]
        gcol = np.array(st["color"], np.float32) * 0.35
        region = region * (1 - 0.55 * glow) + gcol * 0.55 * glow
        region = region * (1 - 0.7 * shadow[..., None])
    scol = stroke_of(img, rect, mask)
    if scol is not None:            # logo asli punya garis tepi -> huruf baru juga
        r = max(2, int(ah * 0.018))
        ring = cv2.dilate((A > 0.3).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2))
        ring = cv2.GaussianBlur(ring.astype(np.float32), (0, 0), 0.8)[..., None]
        region = region * (1 - ring) + np.array(scol, np.float32) * ring
    # isi huruf dengan tekstur logo asli (diregangkan ke area judul baru)
    t = cv2.resize(tex, (aw, ah), interpolation=cv2.INTER_CUBIC)[Y0 - oy:Y1 - oy, X0 - ox:X1 - ox].astype(np.float32)
    # sedikit lebih terang di bagian atas huruf, seperti cat yang terkena cahaya
    grad = np.linspace(1.3, 1.0, t.shape[0], dtype=np.float32)[:, None, None]
    t = np.clip(t * grad, 0, 255)
    region = region * (1 - A[..., None]) + t * A[..., None]
    out[Y0:Y1, X0:X1] = np.clip(region, 0, 255).astype(np.uint8)
    return out


# ---------------------------------------------------------------- 4. judul buatan sendiri (gambar)

def paste_title(img, image_path: str, rect, mask, fit: str = "contain", scale: float = 1.0,
                clean: bool = True, onto=None) -> np.ndarray:
    """Tempel gambar judul buatan sendiri (PNG transparan / JPG) ke kotak judul.
    clean: logo asli di kotak dihapus dulu (latar dibuat ulang)."""
    x, y, w, h = (int(v) for v in rect)
    base = img if onto is None else onto
    out = clean_title(base, [x, y, w, h], mask) if clean else base.copy()
    im = Image.open(image_path).convert("RGBA")
    iw, ih = im.size
    if fit == "stretch":
        nw, nh = w, h
    else:
        s = (max if fit == "cover" else min)(w / iw, h / ih)
        nw, nh = iw * s, ih * s
    nw, nh = max(1, int(nw * scale)), max(1, int(nh * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    ox, oy = x + (w - nw) // 2, y + (h - nh) // 2
    if fit == "cover":           # jangan keluar dari kotak
        cx0, cy0 = max(0, x - ox), max(0, y - oy)
        im = im.crop((cx0, cy0, min(nw, cx0 + w), min(nh, cy0 + h)))
        ox, oy = ox + cx0, oy + cy0
        nw, nh = im.size
    H, W = out.shape[:2]
    X0, Y0, X1, Y1 = max(0, ox), max(0, oy), min(W, ox + nw), min(H, oy + nh)
    if X1 <= X0 or Y1 <= Y0:
        return out
    arr = np.asarray(im)[Y0 - oy:Y1 - oy, X0 - ox:X1 - ox].astype(np.float32)
    a = arr[..., 3:4] / 255.0
    region = out[Y0:Y1, X0:X1].astype(np.float32)
    out[Y0:Y1, X0:X1] = np.clip(region * (1 - a) + arr[..., 2::-1] * a, 0, 255).astype(np.uint8)
    return out


def store_image(src) -> str:
    """Simpan gambar judul (path file / QImage-bytes PNG / PIL Image) ke folder data aplikasi,
    nama = sidik isi (gambar yang sama tidak disimpan dua kali). Mengembalikan path."""
    import hashlib
    import io
    from .paths import data_dir
    if isinstance(src, (bytes, bytearray)):
        im = Image.open(io.BytesIO(src))
    elif isinstance(src, Image.Image):
        im = src
    else:
        im = Image.open(src)
    im = im.convert("RGBA")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    data = buf.getvalue()
    d = data_dir() / "titles"
    d.mkdir(parents=True, exist_ok=True)
    f = d / (hashlib.sha1(data).hexdigest()[:16] + ".png")
    if not f.exists():
        f.write_bytes(data)
    return str(f)
