"""Struktur data proyek: halaman dan blok teks (balon)."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class TextBlock:
    x: int
    y: int
    w: int
    h: int
    source: str = ""          # teks asli hasil OCR
    translation: str = ""     # teks terjemahan (bisa diedit manual)
    kind: str = "bubble"      # bubble | free (teks di luar balon / SFX) | title (logo judul seri)
    sfx: bool = False         # teks spesial besar (huruf kuas/tebal); font dicocokkan otomatis
    vertical: bool = False    # teks asli vertikal (JP/ZH)
    font: str = ""            # kosong = pakai font default
    font_size: int = 0        # 0 = otomatis menyesuaikan kotak
    fit_size: int = 0         # ukuran hasil "Auto" pada render terakhir (info untuk panel)
    color: str = "#000000"
    color2: str = ""          # warna kedua untuk teks gradasi (kosong = warna polos)
    grad_type: str = "linear"  # linear | reflected | radial | split  (lihat core/gradient.py)
    grad_angle: float = 90.0  # arah gradasi (derajat): 90 = atas->bawah, 0 = kiri->kanan
    grad_pos: float = 0.5     # titik tengah peralihan warna (0..1)
    grad_soft: float = 1.0    # kehalusan peralihan (0 = tegas, 1 = halus penuh)
    grad_scope: str = "block"  # block = satu gradasi untuk seluruh teks | line = tiap baris
    stroke_color: str = "#FFFFFF"
    stroke_width: int = 0
    align: str = "center"     # left | center | right
    bold: bool = False
    italic: object = None     # None = ikut pengaturan umum; True/False = khusus balon ini
    case: object = None       # None = ikut pengaturan umum; "upper" | "lower" | "none"
    line_spacing: float = 0.0  # 0 = default (Pengaturan → Teks)
    letter_spacing: float = 0.0  # piksel tambahan antar huruf
    rotation: float = 0.0     # derajat
    max_lines: int = 0        # jumlah baris teks: 0 = otomatis, N = dipaksa tepat N baris (seimbang)
    dx: int = 0               # geser posisi teks (piksel)
    dy: int = 0
    preset: int = 0           # preset teks terakhir yang dipakai (0 = belum)
    clean: bool = True        # hapus teks asli di area ini
    mask_poly: list = field(default_factory=list)  # kontur balon [[x,y],...] opsional
    text_rect: list = field(default_factory=list)  # [x,y,w,h] teks asli hasil deteksi (untuk OCR)
    src_h: int = 0            # tinggi huruf teks asli (px); batas ukuran font otomatis
    font_cat: str = ""        # golongan gaya huruf asli (dialog / dialog-miring / narasi ...) untuk memori font
    title_image: str = ""     # kotak judul: gambar judul buatan sendiri (kosong = dibuat dari teks)
    title_fit: str = "contain"  # contain (muat utuh) | cover (penuhi, terpotong) | stretch (regangkan)
    title_scale: float = 1.0  # skala gambar judul di dalam kotak
    title_keep_bg: bool = False  # True = logo asli TIDAK dihapus sebelum gambar ditempel
    shape: str = ""           # "" = kotak, "oval" = balon oval buatan sendiri (kontur ikut kotak saat diubah)
    note: bool = False        # teks bebas dari alat Teks (catatan / info): tidak di-OCR / diterjemah / dihapus latarnya
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @property
    def rect(self):
        return self.x, self.y, self.w, self.h

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "TextBlock":
        known = {k: v for k, v in d.items() if k in TextBlock.__dataclass_fields__}
        return TextBlock(**known)


def ellipse_poly(x: int, y: int, w: int, h: int, n: int = 72) -> list:
    """Kontur oval di dalam kotak (x, y, w, h) -> [[x, y], ...]."""
    import math
    cx, cy, rx, ry = x + w / 2, y + h / 2, w / 2, h / 2
    return [[int(round(cx + rx * math.cos(2 * math.pi * i / n))), int(round(cy + ry * math.sin(2 * math.pi * i / n)))]
            for i in range(n)]


@dataclass
class Page:
    path: str                         # gambar asli
    blocks: list = field(default_factory=list)
    status: str = "baru"              # baru | dideteksi | di-OCR | diterjemah | selesai
    cleaned_path: str = ""            # cache hasil bersih
    output_path: str = ""             # hasil akhir
    edits: list = field(default_factory=list)   # suntingan manual (healing, hapus area, isi warna)

    @property
    def name(self):
        return Path(self.path).name

    def to_dict(self):
        return {
            "path": self.path,
            "status": self.status,
            "cleaned_path": self.cleaned_path,
            "output_path": self.output_path,
            "edits": self.edits,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @staticmethod
    def from_dict(d: dict) -> "Page":
        return Page(
            path=d["path"],
            status=d.get("status", "baru"),
            cleaned_path=d.get("cleaned_path", ""),
            output_path=d.get("output_path", ""),
            edits=d.get("edits", []) or [],
            blocks=[TextBlock.from_dict(b) for b in d.get("blocks", [])],
        )


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass
class Project:
    pages: list = field(default_factory=list)
    source_lang: str = "ja"
    target_lang: str = "id"
    glossary: dict = field(default_factory=dict)   # istilah tetap: {"先輩": "Senpai"}
    series_title: str = ""    # judul seri terjemahan (untuk logo judul otomatis)
    font_memory: dict = field(default_factory=dict)   # {golongan gaya: path font} dipakai ulang di halaman lain
    export_meta: dict = field(default_factory=dict)   # info seri/chapter untuk Export As (ComicInfo.xml)
    story: dict = field(default_factory=dict)         # memori cerita: {"characters": [...], "notes": ""}
    file: str = ""

    def add_images(self, paths):
        existing = {p.path for p in self.pages}
        for p in sorted(paths, key=natural_key):
            p = str(p)
            if Path(p).suffix.lower() in IMAGE_EXTS and p not in existing:
                self.pages.append(Page(path=p))

    def add_folder(self, folder):
        self.add_images([str(f) for f in Path(folder).iterdir() if f.is_file()])

    def save(self, file: str | None = None):
        if file:
            self.file = file
        data = {
            "version": 1,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "glossary": self.glossary,
            "series_title": self.series_title,
            "font_memory": self.font_memory,
            "export_meta": self.export_meta,
            "story": self.story,
            "pages": [p.to_dict() for p in self.pages],
        }
        Path(self.file).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def load(file: str) -> "Project":
        d = json.loads(Path(file).read_text(encoding="utf-8"))
        return Project(
            pages=[Page.from_dict(p) for p in d.get("pages", [])],
            source_lang=d.get("source_lang", "ja"),
            target_lang=d.get("target_lang", "id"),
            glossary=d.get("glossary", {}),
            series_title=d.get("series_title", ""),
            font_memory=d.get("font_memory", {}) or {},
            export_meta=d.get("export_meta", {}) or {},
            story=d.get("story", {}) or {},
            file=file,
        )


def natural_key(s):
    """Urutkan 'page2' sebelum 'page10'."""
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]
