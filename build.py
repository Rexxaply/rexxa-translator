"""Build Rexxa Translator menjadi aplikasi Windows + paket rilis.

  python build.py              build lengkap (.exe + app/) ke dist/RexxaTranslator
  python build.py --release    + buat paket rilis di dist/: zip penuh, zip kode, update.json
                               (dipakai GitHub Actions)
  python build.py --app-only   hanya paket kode (tanpa PyInstaller) — untuk menguji update cepat

Hasil di dist/:
  RexxaTranslator/                    folder aplikasi siap pakai
  RexxaTranslator-X.Y.Z-win64.zip     aplikasi lengkap (untuk instal baru / update penuh)
  RexxaTranslator-app-X.Y.Z.zip       hanya folder app/ (update cepat)
  update.json                         info rilis yang dibaca updater di aplikasi
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
NAME = "RexxaTranslator"
APP_PARTS = ["core", "gui", "assets", "fonts"]          # isi folder app/
DEFAULT_REPO = "Rexxaply/rexxa-translator"


def app_version() -> str:
    m = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "core" / "version.py").read_text(encoding="utf-8"))
    return m.group(1)


def engine_version() -> int:
    m = re.search(r"^ENGINE_VERSION\s*=\s*(\d+)", (ROOT / "main.py").read_text(encoding="utf-8"), re.M)
    return int(m.group(1))


def release_notes(ver: str) -> str:
    """Ambil bagian '## X.Y.Z' dari CHANGELOG.md."""
    p = ROOT / "CHANGELOG.md"
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    m = re.search(rf"^##\s*v?{re.escape(ver)}\b.*?$(.*?)(?=^##\s|\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


# Font komik berlisensi bebas (SIL OFL) yang ikut dibundel sebagai default.
BUNDLED_FONTS = {
    "ComicNeue-BoldItalic.ttf": "https://github.com/google/fonts/raw/main/ofl/comicneue/ComicNeue-BoldItalic.ttf",
    "ComicNeue-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/comicneue/ComicNeue-Bold.ttf",
    "ComicNeue-OFL.txt": "https://github.com/google/fonts/raw/main/ofl/comicneue/OFL.txt",
}


def fetch_fonts():
    """Unduh font bundel ke fonts/ bila belum ada (butuh internet; dilewati bila gagal)."""
    import urllib.request
    d = ROOT / "fonts"
    d.mkdir(exist_ok=True)
    for name, url in BUNDLED_FONTS.items():
        dst = d / name
        if dst.exists() and dst.stat().st_size > 0:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "RexxaTranslator-build"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if name.endswith(".ttf") and data[:4] not in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
                raise ValueError("bukan file font")
            dst.write_bytes(data)
            print(f"Font diunduh: {name}")
        except Exception as e:
            print(f"[!] Gagal mengunduh {name}: {e} — aplikasi memakai font cadangan.")


def all_release_notes() -> list[dict]:
    """Semua bagian '## X.Y.Z' dari CHANGELOG.md, terbaru dulu: [{"version","notes"}]."""
    p = ROOT / "CHANGELOG.md"
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"^##\s*v?(\d+(?:\.\d+)*)\b.*?$(.*?)(?=^##\s|\Z)", text, re.S | re.M):
        out.append({"version": m.group(1), "notes": m.group(2).strip()})
    return out


def has(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def copy_app(dest: Path):
    """Salin kode aplikasi ke <dest>/ (tanpa cache)."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    ign = shutil.ignore_patterns("__pycache__", "*.pyc", "settings.json")
    for part in APP_PARTS:
        src = ROOT / part
        if src.is_dir():
            shutil.copytree(src, dest / part, ignore=ign)


def pyinstaller():
    args = [sys.executable, "-m", "PyInstaller", str(ROOT / "main.py"), "--name", NAME, "--noconfirm",
            "--windowed", "--onedir", "--clean", "--icon", str(ROOT / "assets" / "icon.ico"),
            "--distpath", str(DIST), "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
            "--collect-submodules", "deep_translator"]
    extra = []
    if has("manga_ocr"):
        extra += ["--collect-all", "manga_ocr", "--collect-all", "unidic_lite", "--collect-all", "fugashi"]
    if has("easyocr"):
        extra += ["--collect-all", "easyocr"]
    if has("simple_lama_inpainting"):
        extra += ["--collect-all", "simple_lama_inpainting"]
    if has("torchvision"):
        # operator C torchvision (nms) wajib ikut, kalau tidak: "torchvision::nms does not exist"
        extra += ["--collect-all", "torchvision", "--collect-binaries", "torch"]
    print("Paket AI ikut dibundel:", "ya" if extra else "tidak (OCR/LaMa tidak tersedia di .exe)")
    subprocess.run(args + extra, check=True)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def zip_dir(src: Path, zip_path: Path, arc_root: str):
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(src.rglob("*")):
            if f.is_file():
                z.write(f, f"{arc_root}/{f.relative_to(src).as_posix()}")
    return zip_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--app-only", action="store_true")
    a = ap.parse_args()

    ver, eng = app_version(), engine_version()
    tag = os.environ.get("GITHUB_REF_NAME", "")
    if a.release and tag.startswith("v") and tag[1:] != ver:
        sys.exit(f"Tag {tag} tidak sama dengan __version__ {ver} di core/version.py — samakan dulu.")
    print(f"Rexxa Translator {ver} (mesin v{eng})")
    DIST.mkdir(exist_ok=True)
    app_dir = DIST / NAME / "app"

    fetch_fonts()
    if not a.app_only:
        pyinstaller()
    copy_app(app_dir)
    print(f"Aplikasi: {DIST / NAME}")

    if not (a.release or a.app_only):
        return

    repo = os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPO)
    base_url = f"https://github.com/{repo}/releases/download/v{ver}"
    meta = {"version": ver, "engine": eng, "notes": release_notes(ver), "changelog": all_release_notes()}

    app_zip = zip_dir(app_dir, DIST / f"{NAME}-app-{ver}.zip", "app")
    meta["app"] = {"url": f"{base_url}/{app_zip.name}", "sha256": sha256(app_zip), "size": app_zip.stat().st_size}
    if not a.app_only:
        full_zip = zip_dir(DIST / NAME, DIST / f"{NAME}-{ver}-win64.zip", NAME)
        meta["full"] = {"url": f"{base_url}/{full_zip.name}", "sha256": sha256(full_zip),
                        "size": full_zip.stat().st_size}
    (DIST / "update.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (DIST / "release-notes.md").write_text(
        (meta["notes"] or f"Rexxa Translator {ver}") +
        "\n\n---\n**Instal baru:** unduh `" + f"{NAME}-{ver}-win64.zip" + "`, ekstrak, buka `RexxaTranslator.exe`.\n"
        "**Sudah terpasang:** aplikasi akan menawarkan update otomatis.\n", encoding="utf-8")
    for f in sorted(DIST.glob("*")):
        if f.is_file():
            print(f"  {f.name:45s} {f.stat().st_size / 1048576:8.1f} MB")


if __name__ == "__main__":
    main()
