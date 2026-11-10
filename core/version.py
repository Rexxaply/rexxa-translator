"""Versi aplikasi & pengecekan update.

Rilis di GitHub (dibuat otomatis oleh .github/workflows/release.yml saat versi di bawah naik) berisi:
  update.json                       -> {"version","engine","app":{url,sha256,size},"full":{...},"notes"}
  RexxaTranslator-app-X.Y.Z.zip     -> hanya folder app/ (kode)        — update cepat, beberapa ratus KB
  RexxaTranslator-X.Y.Z-win64.zip   -> aplikasi lengkap (mesin + kode) — update penuh / instal baru

Saat merilis: naikkan __version__ di sini, tulis catatan di CHANGELOG.md, commit, lalu push ke main.
"""
from __future__ import annotations

import os
import re

import requests

__version__ = "2.0.3"

DEFAULT_REPO = "Rexxaply/rexxa-translator"


def engine_version() -> int | None:
    """Versi mesin .exe yang sedang berjalan (None = dijalankan dari source)."""
    v = os.environ.get("REXXA_ENGINE")
    return int(v) if v and v.isdigit() else None


def parse_version(v: str) -> tuple:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - min(3, len(nums)))


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def _asset(d, name_pred):
    for a in d.get("assets", []):
        if name_pred(a.get("name", "")):
            return a
    return None


def fetch_latest(source: str, timeout: int = 10) -> dict:
    """Kembalikan info rilis terbaru:
    {"version","notes","page","engine","app":{url,sha256,size}|None,"full":{...}|None}"""
    source = (source or "").strip()
    if not source:
        raise ValueError("Sumber update belum diatur (Pengaturan → Update).")
    headers = {"User-Agent": "RexxaTranslator-updater", "Accept": "application/vnd.github+json"}

    if re.fullmatch(r"[\w.-]+/[\w.-]+", source):        # format owner/repo GitHub
        r = requests.get(f"https://api.github.com/repos/{source}/releases/latest",
                         headers=headers, timeout=timeout)
        if r.status_code == 404:
            raise ValueError("Repo tidak ditemukan, private, atau belum punya rilis.")
        r.raise_for_status()
        d = r.json()
        info = {"version": d.get("tag_name", ""), "notes": d.get("body", "") or "",
                "page": d.get("html_url", ""), "engine": None, "app": None, "full": None}
        meta = _asset(d, lambda n: n == "update.json")
        if meta:
            m = requests.get(meta["browser_download_url"], headers={"User-Agent": headers["User-Agent"]},
                             timeout=timeout)
            m.raise_for_status()
            info.update({k: v for k, v in m.json().items() if k in ("version", "engine", "app", "full", "notes", "changelog")
                         and v not in (None, "")})
        else:  # rilis lama/manual tanpa update.json: pakai zip apa pun sebagai unduhan penuh
            z = _asset(d, lambda n: n.lower().endswith(".zip"))
            if z:
                info["full"] = {"url": z["browser_download_url"], "sha256": "", "size": z.get("size", 0)}
        return info

    r = requests.get(source, headers={"User-Agent": headers["User-Agent"]}, timeout=timeout)
    r.raise_for_status()
    d = r.json()
    full = d.get("full") or ({"url": d["url"], "sha256": "", "size": 0} if d.get("url") else None)
    return {"version": str(d.get("version", "")), "notes": d.get("notes", ""), "page": d.get("url", ""),
            "engine": d.get("engine"), "app": d.get("app"), "full": full}


def changelog_between(info: dict, current: str = __version__, limit: int = 5) -> list[dict]:
    """Catatan versi SETELAH versi terpasang sampai versi terbaru (terbaru dulu, maks. `limit`)."""
    items = [c for c in (info.get("changelog") or [])
             if is_newer(c.get("version", ""), current) and not is_newer(c.get("version", ""), info.get("version", ""))]
    if not items and info.get("notes"):       # rilis lama tanpa daftar changelog
        items = [{"version": (info.get("version") or "").lstrip("vV"), "notes": info["notes"]}]
    return sorted(items, key=lambda c: parse_version(c["version"]), reverse=True)[:limit]


def update_kind(info: dict) -> str:
    """'app' = cukup ganti kode, 'full' = unduh aplikasi lengkap, 'manual' = buka halaman rilis."""
    eng = engine_version()
    need = info.get("engine")
    if info.get("app") and eng is not None and need is not None and int(need) <= eng:
        return "app"
    if info.get("app") and eng is None:          # dari source: kode saja sudah cukup
        return "app"
    if info.get("full") and os.name == "nt" and eng is not None:
        return "full"
    return "manual"
