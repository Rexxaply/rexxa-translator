"""Koreksi otomatis salah baca OCR untuk teks Inggris (komik / manga terjemahan Inggris).

OCR sering tertukar pada huruf yang bentuknya mirip, apalagi huruf komik yang miring / tebal:
  C↔G, O↔0/Q/D, I↔l/1/|/!, S↔5, B↔8, rn↔m, vv↔w, ...
dan tanda seru di akhir sering terbaca sebagai "I", "l", "Ir", "!r".

Cara kerja: setiap kata yang TIDAK ada di kamus dicari pasangannya di kamus dengan mengganti huruf
yang mirip bentuknya (lalu, bila tidak ketemu, satu perubahan huruf apa pun). Kata hanya diganti bila
hasilnya jelas (satu kandidat terbaik), jadi nama tokoh / kata asing yang tidak dikenali tidak dirusak.
Kamus: assets/en_words.txt.gz (dari kamus Tesseract, Apache-2.0).
"""
from __future__ import annotations

import gzip
import re
from functools import lru_cache

# huruf yang sering tertukar oleh OCR (huruf kecil); nilai = kemungkinan huruf aslinya
CONFUSE = {
    "g": "cqo", "c": "goe", "e": "co", "o": "0qdcau", "q": "og", "d": "o",
    "i": "l1!jt", "l": "i1!t", "1": "il", "|": "il", "!": "il", "j": "i", "t": "il",
    "s": "5", "5": "s", "b": "8h", "8": "b", "h": "bn", "n": "hu", "u": "nv", "v": "uy",
    "0": "o", "a": "o", "r": "n", "y": "v", "z": "2", "2": "z", "k": "x", "x": "k",
}
# pasangan yang SANGAT sering tertukar di huruf komik -> biaya lebih murah (menang saat seri)
STRONG = {("g", "c"), ("0", "o"), ("1", "l"), ("1", "i"), ("l", "i"), ("i", "l"), ("|", "l"), ("|", "i"),
          ("5", "s"), ("8", "b"), ("!", "i"), ("!", "l"), ("c", "e"), ("q", "o")}
# kata yang memang berakhiran I (jangan diubah jadi tanda seru di akhir kalimat)
ENDS_I = set("hi taxi samurai sushi hawaii wasabi senpai sensei kai mai yui ai alibi bikini broccoli chili ski "
             "safari spaghetti salami tsunami origami kiwi mini semi sashimi kanji yuki mari teriyaki sukiyaki "
             "ramen udon gyoza onigiri kami oni yokai hentai kawaii itadakimasu uchi chi pi xi psi".split())
# singkatan yang apostrofnya hilang saat OCR (huruf kapital komik)
CONTRACT = {"tll": "i'll", "1ll": "i'll", "|ll": "i'll", "im": "i'm", "tm": "i'm", "1m": "i'm", "lm": "i'm",
            "ive": "i've", "tve": "i've", "1ve": "i've", "td": None, "ive": "i've", "dont": "don't",
            "cant": "can't", "wont": "won't", "thats": "that's", "youre": "you're", "theyre": "they're",
            "isnt": "isn't", "didnt": "didn't", "doesnt": "doesn't", "wasnt": "wasn't", "arent": "aren't",
            "couldnt": "couldn't", "wouldnt": "wouldn't", "shouldnt": "shouldn't", "havent": "haven't",
            "hasnt": "hasn't", "whats": "what's", "wheres": "where's", "theres": "there's", "hes": "he's",
            "shes": "she's", "youve": "you've", "youll": "you'll", "theyll": "they'll", "weve": "we've",
            "lets": None, "aint": "ain't", "wouldve": "would've", "couldve": "could've",
            "shouldve": "should've", "whos": "who's", "hows": "how's", "werent": "weren't"}
MULTI = [("rn", "m"), ("m", "rn"), ("vv", "w"), ("w", "vv"), ("cl", "d"), ("ii", "u"), ("li", "h")]
ALPHA = "abcdefghijklmnopqrstuvwxyz"
TOKEN = re.compile(r"[A-Za-z0-9|!']+")
_TAIL = re.compile(r"(?<=[A-Za-z]{2})([Il1|][r!]?|![r]|!!r|I!+)$")


@lru_cache(maxsize=1)
def _words():
    from .paths import code_dir
    common, rare = set(), set()
    try:
        f = code_dir() / "assets" / "en_words.txt.gz"
        cur = common
        for line in gzip.decompress(f.read_bytes()).decode("utf-8").splitlines():
            if line.startswith("#"):
                if line == "#rare":
                    cur = rare
                continue
            if line:
                cur.add(line)
    except Exception:
        pass
    return common, common | rare


def available() -> bool:
    return bool(_words()[0])


def _known(w: str) -> bool:
    w = w.lower().strip("'")
    if not w:
        return True
    acc = _words()[1]
    if w in acc:
        return True
    for suf in ("'s", "s'", "'re", "'ll", "'ve", "'d", "'m", "n't"):     # bentuk singkatan
        if w.endswith(suf) and w[: -len(suf)] in acc:
            return True
    return False


def _is_common(w: str) -> bool:
    return w in _words()[0]


def _candidates(w: str):
    """{kata: biaya} kandidat untuk kata w (huruf kecil). Kata umum lebih murah dari kata langka."""
    common, acc = _words()
    out = {}

    def add(c, cost):
        if c in common:
            pass
        elif c in acc and len(c) >= 5:
            cost += 0.6
        else:
            return
        if c not in out or cost < out[c]:
            out[c] = cost

    n = len(w)
    # 1) satu / dua huruf mirip-bentuk
    for i, ch in enumerate(w):
        for r in CONFUSE.get(ch, ""):
            c1 = w[:i] + r + w[i + 1:]
            k1 = 0.7 if (ch, r) in STRONG else 1.0
            add(c1, k1)
            for j in range(i + 1, n):
                for r2 in CONFUSE.get(w[j], ""):
                    add(c1[:j] + r2 + c1[j + 1:], k1 + (0.7 if (w[j], r2) in STRONG else 1.0))
    for a, b in MULTI:
        k = w.find(a)
        while k >= 0:
            add(w[:k] + b + w[k + len(a):], 1.0)
            k = w.find(a, k + 1)
    odd = any(c in w for c in "0158|!")
    if out or not (odd or n >= 8):
        return out
    # 2) satu perubahan huruf apa pun -- hanya kata panjang / yang jelas berisi karakter aneh,
    #    supaya nama tokoh tidak "dikoreksi" jadi kata lain
    for i in range(n):
        add(w[:i] + w[i + 1:], 2.2)                         # huruf berlebih
        for r in ALPHA:
            add(w[:i] + r + w[i + 1:], 2.5)                 # huruf salah
            add(w[:i] + r + w[i:], 2.5)                     # huruf hilang
    return out


def _best(w: str):
    cands = _candidates(w)
    if not cands:
        return None
    best = min(cands.values())
    top = sorted(c for c, v in cands.items() if abs(v - best) < 1e-6)
    if len(top) == 1:
        return top[0], best
    return None                                            # ragu: jangan diganti


def _case_like(src: str, word: str) -> str:
    letters = [c for c in src if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) >= max(1, len(letters) * 0.6):
        return word.upper()
    if src[:1].isupper():
        return word[:1].upper() + word[1:]
    return word


def _fix_core(core: str) -> str:
    """Perbaiki satu kata (tanpa tanda baca di ujung)."""
    w = core.lower()
    c = CONTRACT.get(w)
    if c and core.isupper():
        return c.upper()
    odd = any(c in w for c in "0158|!")
    if len(w) < 2 or (len(w) < 3 and not odd):
        return core
    if _is_common(w) or (_known(w) and not odd and not _is_common_close(w)):
        return core
    if not w.replace("'", "").isalpha() and not odd:
        return core
    got = _best(w)
    if not got:
        return core
    cand, cost = got
    if _known(w) and cost > 1.0:          # kata langka yang dikenal: hanya koreksi yang sangat jelas
        return core
    if cost > 1.0 and not odd and len(w) < 8:
        return core                       # 2 huruf berubah di kata pendek: mungkin logat sengaja ("BESHT")
    return _case_like(core, cand)


def _is_common_close(w: str) -> bool:
    """Kata langka (mis. 'glear') yang SATU huruf-mirip dari kata umum (mis. 'clear')."""
    got = _best(w)
    return bool(got and got[1] <= 1.0 and got[0] in _words()[0])


def _fix_word(tok: str, last: bool = False) -> str:
    if not any(c.isalpha() for c in tok):
        return tok
    # "HERI" di akhir teks berhuruf kapital = "HER!" (tanda seru terbaca sebagai I)
    if last and len(tok) >= 3 and tok.isupper() and tok[-1] == "I" and tok.lower() not in ENDS_I \
            and _is_common(tok[:-1].lower()) and not tok.endswith("II"):
        return tok[:-1] + "!"
    core = tok
    while len(core) > 2 and core[0] in "|!":                # "|" di depan kata = sisa garis balon
        core = core[1:]
    tail = ""
    m = _TAIL.search(core)
    if m and not _is_common(core.lower()):
        stem = core[: m.start()]
        fixed_stem = _fix_core(stem)
        if _known(fixed_stem.lower()) or _known(stem.lower()):
            return fixed_stem + "!" * min(3, max(1, m.group(0).count("!")))
    while len(core) > 2 and core[-1] in "!|":
        tail += "!"
        core = core[:-1]
    return _fix_core(core) + tail


def plausible(text: str, lang: str = "en") -> bool:
    """Apakah hasil OCR terlihat seperti teks sungguhan (bukan rambut / raster yang terbaca huruf)?"""
    t = (text or "").strip()
    letters = sum(c.isalpha() for c in t)
    if letters == 1 and re.fullmatch(r"[A-Za-z](\.\.\.|[!?]+|…)", t):
        return True                    # "I...", "A!", "O?"
    if letters < 2:
        return False
    if lang != "en" or not available():
        return True
    toks = re.findall(r"[A-Za-z']+", t)
    long_ = [w.strip("'") for w in toks if len(w.strip("'")) >= 3]
    if long_:
        def good(w):
            lw = w.lower()
            return _is_common(lw) or lw in CONTRACT or (len(lw) >= 5 and _known(lw)) or \
                _is_common(_fix_core(w).lower())
        if len(long_) == 1 and len(toks) <= 2:
            # satu kata (nama tokoh "FORSINA!?", seruan "Kyaaa!") -> terima bila terlihat seperti kata
            w = long_[0]
            return good(w) or any(c in t for c in "!?….~") or w[:1].isupper()
        return sum(good(w) for w in long_) / len(long_) >= 0.6
    # hanya kata 1-2 huruf: terima seruan pendek ("OH!", "WH...", "HM?") / huruf kapital
    return any(c in t for c in "!?…") or "..." in t or any(len(w) == 2 and w.isupper() for w in toks)


def fix(text: str, lang: str = "en") -> str:
    """Perbaiki salah baca OCR pada teks (hanya bahasa Inggris)."""
    if lang != "en" or not text or not available():
        return text
    toks = list(TOKEN.finditer(text))
    last_i = len(toks) - 1
    parts, pos = [], 0
    for i, m in enumerate(toks):
        rest = text[m.end():].strip()
        is_last = i == last_i and (not rest or all(c in ".!?…\"'" for c in rest)) and text.upper() == text
        parts.append(text[pos:m.start()])
        parts.append(_fix_word(m.group(0), last=is_last))
        pos = m.end()
    parts.append(text[pos:])
    out = "".join(parts)
    out = re.sub(r"(?<![A-Za-z'])i(?=$|[\s'.,!?…])", "I", out)       # kata ganti "i" -> "I"
    # tanda baca: "!r" / " I!" sisa di akhir kalimat
    out = re.sub(r"\s+([!?])", r"\1", out)
    out = re.sub(r"!{4,}", "!!!", out)
    return out
