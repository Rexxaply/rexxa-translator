"""Mode baris perintah (batch tanpa GUI).

Contoh:
  python cli.py "D:/manga/chapter 12" --src ja --tgt id
  python cli.py halaman01.png --engine llm --out hasil
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import pipeline  # noqa: E402
from core.models import Project  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Rexxa Translator CLI")
    ap.add_argument("input", nargs="+", help="folder chapter atau file gambar")
    ap.add_argument("--src", default="ja", help="bahasa sumber: ja ko zh zh-tw en")
    ap.add_argument("--tgt", default="id", help="bahasa tujuan: id en ms ...")
    ap.add_argument("--engine", choices=["google", "deepl", "llm"], help="engine terjemahan")
    ap.add_argument("--detect", choices=["bubble", "easyocr", "hybrid"])
    ap.add_argument("--ocr", choices=["auto", "manga-ocr", "easyocr"])
    ap.add_argument("--clean", choices=["auto", "fill", "opencv", "lama"])
    ap.add_argument("--out", help="folder output")
    ap.add_argument("--save", help="simpan proyek .mtproj (bisa dibuka & diedit di GUI)")
    a = ap.parse_args()

    st = pipeline.load_settings()
    for key, val in (("translate_engine", a.engine), ("detect_mode", a.detect), ("ocr_engine", a.ocr),
                     ("clean_method", a.clean), ("output_dir", a.out)):
        if val:
            st[key] = val

    proj = Project(source_lang=a.src, target_lang=a.tgt)
    for p in a.input:
        proj.add_folder(p) if os.path.isdir(p) else proj.add_images([p])
    if not proj.pages:
        sys.exit("Tidak ada gambar ditemukan.")

    for i, page in enumerate(proj.pages, 1):
        print(f"[{i}/{len(proj.pages)}]", end=" ")
        try:
            pipeline.process_page(page, proj, st)
        except ImportError as e:
            sys.exit(f"Modul belum terpasang: {e}. Jalankan install_ai.bat")
        except Exception as e:
            print(f"  gagal: {e}")
    if a.save:
        proj.save(a.save)
        print("Proyek disimpan:", a.save)


if __name__ == "__main__":
    main()
