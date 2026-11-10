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
    kind: str = "bubble"      # bubble | free (teks di luar balon / SFX)
    vertical: bool = False    # teks asli vertikal (JP/ZH)
    font: str = ""            # kosong = pakai font default
    font_size: int = 0        # 0 = otomatis menyesuaikan kotak
    color: str = "#000000"
    stroke_color: str = "#FFFFFF"
    stroke_width: int = 0
    align: str = "center"     # left | center | right
    bold: bool = False
    italic: object = None     # None = ikut pengaturan umum; True/False = khusus balon ini
    case: object = None       # None = ikut pengaturan umum; "upper" | "lower" | "none"
    line_spacing: float = 0.0  # 0 = default (Pengaturan → Teks)
    letter_spacing: float = 0.0  # piksel tambahan antar huruf
    rotation: float = 0.0     # derajat
    dx: int = 0               # geser posisi teks (piksel)
    dy: int = 0
    preset: int = 0           # preset teks terakhir yang dipakai (0 = belum)
    clean: bool = True        # hapus teks asli di area ini
    mask_poly: list = field(default_factory=list)  # kontur balon [[x,y],...] opsional
    text_rect: list = field(default_factory=list)  # [x,y,w,h] teks asli hasil deteksi (untuk OCR)
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


@dataclass
class Page:
    path: str                         # gambar asli
    blocks: list = field(default_factory=list)
    status: str = "baru"              # baru | dideteksi | di-OCR | diterjemah | selesai
    cleaned_path: str = ""            # cache hasil bersih
    output_path: str = ""             # hasil akhir

    @property
    def name(self):
        return Path(self.path).name

    def to_dict(self):
        return {
            "path": self.path,
            "status": self.status,
            "cleaned_path": self.cleaned_path,
            "output_path": self.output_path,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @staticmethod
    def from_dict(d: dict) -> "Page":
        return Page(
            path=d["path"],
            status=d.get("status", "baru"),
            cleaned_path=d.get("cleaned_path", ""),
            output_path=d.get("output_path", ""),
            blocks=[TextBlock.from_dict(b) for b in d.get("blocks", [])],
        )


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass
class Project:
    pages: list = field(default_factory=list)
    source_lang: str = "ja"
    target_lang: str = "id"
    glossary: dict = field(default_factory=dict)   # istilah tetap: {"先輩": "Senpai"}
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
            file=file,
        )


def natural_key(s):
    """Urutkan 'page2' sebelum 'page10'."""
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]
