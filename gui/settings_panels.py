"""Tab Pengaturan: Teks (preset), Shortcut, Data."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QKeySequenceEdit, QLabel,
                               QMessageBox, QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget)

from core import datastore as DS
from core import pipeline, translator, typeset
from . import shortcuts as SC
from .alert import Alert, MessageBox as QMessageBox  # noqa: E402,F811  (semua alert bergaya Rexxa)

DIM = "color:#8a8e9a;"


def _scroll(inner: QWidget) -> QScrollArea:
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.NoFrame)
    sc.setWidget(inner)
    return sc


def _font_items(combo: QComboBox, current: str):
    combo.blockSignals(True)
    combo.clear()
    combo.addItem("(otomatis)", "")
    for f in typeset.list_fonts():
        combo.addItem(typeset.font_name(f), f)
    i = combo.findData(current)
    if i < 0 and current:
        combo.addItem(Path(current).stem, current)
        i = combo.count() - 1
    combo.setCurrentIndex(max(0, i))
    combo.blockSignals(False)


# ====================================================================== Teks
class TextPanel(QWidget):
    """Preset 1–5 (font, tebal, miring, KAPITAL/kecil), ukuran font default, penamaan file export.
    Preset 1 = gaya default semua balon. Tombol 1–5 di panel Tipografi menerapkan preset ke balon."""

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        head = QLabel("Preset gaya teks. <b>Preset 1</b> dipakai untuk semua balon; preset lain diterapkan per "
                      "balon lewat tombol <b>1–5</b> di panel Tipografi.")
        head.setWordWrap(True)
        head.setStyleSheet(DIM)
        v.addWidget(head)

        g = QGridLayout()
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(8)
        self.rows = []
        for n, p in enumerate(pipeline.presets(settings), 1):
            lbl = QLabel(f"Preset {n}" + ("  <span style='color:#ff4d6d'>default</span>" if n == 1 else ""))
            font = QComboBox()
            _font_items(font, p["font"])
            b = self._toggle("B", "Tebal", p["bold"])
            it = self._toggle("I", "Miring", p["italic"])
            up = self._toggle("AA", "HURUF KAPITAL", p["case"] == "upper")
            lo = self._toggle("aa", "huruf kecil", p["case"] == "lower")
            up.toggled.connect(lambda on, lo=lo: on and lo.setChecked(False))   # KAPITAL / kecil saling eksklusif
            lo.toggled.connect(lambda on, up=up: on and up.setChecked(False))
            for c, wdg in enumerate((lbl, font, b, it, up, lo)):
                g.addWidget(wdg, n - 1, c)
            self.rows.append((font, b, it, up, lo))
        g.setColumnStretch(1, 1)
        v.addLayout(g)

        v.addSpacing(10)
        g2 = QGridLayout()
        g2.addWidget(QLabel("Ukuran font"), 0, 0)
        g2.addWidget(QLabel("Jarak baris"), 0, 1)
        g2.addWidget(QLabel("Penamaan file export"), 0, 2)
        self.size = QComboBox()
        self.size.addItem("Auto-Fit (menyesuaikan balon)", 0)
        for n in (12, 14, 16, 18, 20, 22, 24, 28, 32, 36, 40, 48, 56, 64, 72):
            self.size.addItem(f"{n} px", n)
        self.size.setCurrentIndex(max(0, self.size.findData(int(settings.get("default_font_size", 0) or 0))))
        self.naming = QComboBox()
        for k, label in pipeline.EXPORT_NAMING.items():
            self.naming.addItem(label, k)
        self.naming.setCurrentIndex(max(0, self.naming.findData(settings.get("export_naming", "original"))))
        self.lsp = QDoubleSpinBox()
        self.lsp.setRange(0.8, 2.5)
        self.lsp.setSingleStep(0.05)
        self.lsp.setDecimals(2)
        self.lsp.setValue(float(settings.get("line_spacing", 1.2) or 1.2))
        self.lsp.setToolTip("1.0 = rapat. Lettering manga umumnya 1.15–1.25.")
        g2.addWidget(self.size, 1, 0)
        g2.addWidget(self.lsp, 1, 1)
        g2.addWidget(self.naming, 1, 2)
        v.addLayout(g2)
        v.addStretch()

    @staticmethod
    def _toggle(text, tip, on):
        b = QToolButton(text=text)
        b.setObjectName("styleToggle")
        b.setCheckable(True)
        b.setChecked(bool(on))
        b.setToolTip(tip)
        b.setFixedSize(34, 28)
        if text == "B":
            f = b.font(); f.setBold(True); b.setFont(f)
        if text == "I":
            f = b.font(); f.setItalic(True); b.setFont(f)
        return b

    def refresh_fonts(self):
        for font, *_ in self.rows:
            _font_items(font, font.currentData() or "")

    def default_font(self) -> str:
        return self.rows[0][0].currentData() or ""

    def set_default_font(self, path: str):
        combo = self.rows[0][0]
        _font_items(combo, path)

    def values(self) -> dict:
        presets = []
        for font, b, it, up, lo in self.rows:
            presets.append({"font": font.currentData() or "", "bold": b.isChecked(), "italic": it.isChecked(),
                            "case": "upper" if up.isChecked() else "lower" if lo.isChecked() else "none"})
        return {"text_presets": presets, "default_font_size": self.size.currentData(),
                "line_spacing": round(self.lsp.value(), 2),
                "export_naming": self.naming.currentData()}


# ====================================================================== Shortcut
class ShortcutPanel(QWidget):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        v = QVBoxLayout(inner)
        tip = QLabel("Klik kolom pintasan lalu tekan kombinasi tombol yang baru. "
                     "Pintasan bertanda ◆ hanya aktif saat fokus di gambar.")
        tip.setWordWrap(True)
        tip.setStyleSheet(DIM)
        v.addWidget(tip)
        cur = SC.current(settings)
        self.edits = {}
        group = None
        box = None
        for sid, grp, label, default, local in SC.SHORTCUTS:
            if grp != group:
                group = grp
                card = QFrame()
                card.setObjectName("card")
                box = QGridLayout(card)
                box.setColumnStretch(0, 1)
                title = QLabel(grp.upper())
                title.setStyleSheet("font-weight:600; font-size:8.5pt; color:#c9ccd4;")
                box.addWidget(title, 0, 0, 1, 3)
                v.addWidget(card)
            r = box.rowCount()
            box.addWidget(QLabel(("◆ " if local else "") + label), r, 0)
            ed = QKeySequenceEdit(QKeySequence(cur.get(sid, "")))
            if hasattr(ed, "setMaximumSequenceLength"):
                ed.setMaximumSequenceLength(1)
            ed.setFixedWidth(150)
            ed.setToolTip(f"Default: {default}")
            clr = QToolButton(text="×")
            clr.setToolTip("Kosongkan")
            clr.clicked.connect(ed.clear)
            box.addWidget(ed, r, 1)
            box.addWidget(clr, r, 2)
            self.edits[sid] = ed
        row = QHBoxLayout()
        reset = QPushButton("Kembalikan semua ke default")
        reset.clicked.connect(self.reset_defaults)
        row.addStretch()
        row.addWidget(reset)
        v.addLayout(row)
        v.addStretch()
        outer.addWidget(_scroll(inner))

    def reset_defaults(self):
        for sid, ed in self.edits.items():
            ed.setKeySequence(QKeySequence(SC.DEFAULTS[sid]))

    def mapping(self) -> dict:
        return {sid: ed.keySequence().toString(QKeySequence.PortableText) for sid, ed in self.edits.items()}

    def values(self) -> dict:
        """Hanya yang berbeda dari default (supaya default baru di versi mendatang tetap terpakai)."""
        return {"shortcuts": {k: v for k, v in self.mapping().items() if v != SC.DEFAULTS[k]}}

    def is_default(self) -> bool:
        return not self.values()["shortcuts"]


# ====================================================================== Data
class DataPanel(QWidget):
    def __init__(self, settings: dict, project=None, shortcut_panel: ShortcutPanel | None = None,
                 on_factory_reset=None, parent=None):
        super().__init__(parent)
        self.settings, self.project = settings, project
        self.sc_panel, self.on_factory_reset = shortcut_panel, on_factory_reset
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        self.v = QVBoxLayout(inner)
        self.cards = {}
        self._card("cache_tr", "Cache terjemahan",
                   "Terjemahan yang disimpan supaya teks yang sama tidak dikirim lagi ke mesin penerjemah "
                   "(hemat token). Kotak balon tidak ikut terhapus.", "Hapus", self._clear_tr)
        self._card("cache", "Cache gambar & data proses",
                   "Gambar bersih sementara proyek yang terbuka, unduhan update, dan log. Dibuat ulang otomatis.",
                   "Hapus", self._clear_cache)
        self._card("models", "Model AI yang diunduh",
                   "Model OCR & hapus teks. Akan diunduh lagi saat dipakai berikutnya.", "Hapus", self._clear_models)
        self._card("shortcuts", "Shortcut keyboard", "Kembalikan semua pintasan ke default.", "Reset",
                   self._reset_shortcuts)
        self._card("reset", "Reset aplikasi",
                   "Kembalikan semua pengaturan ke awal (termasuk API key), hapus cache terjemahan & shortcut. "
                   "Font yang diinstal dan model AI tidak dihapus.", "Reset", self._factory_reset, danger=True)
        self.v.addStretch()
        outer.addWidget(_scroll(inner))
        self.refresh()

    def _card(self, key, title, desc, btn_text, slot, danger=False):
        card = QFrame()
        card.setObjectName("card")
        g = QGridLayout(card)
        t = QLabel(title)
        t.setStyleSheet("font-weight:600;" + ("color:#ff6b6b;" if danger else ""))
        d = QLabel(desc)
        d.setWordWrap(True)
        d.setStyleSheet(DIM + "font-size:8.5pt;")
        info = QLabel("")
        info.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        info.setStyleSheet("font-weight:600;" + ("color:#ff6b6b;" if danger else ""))
        b = QPushButton(btn_text)
        b.setFixedWidth(90)
        if danger:
            b.setStyleSheet("QPushButton { background:#e5383b; color:white; border:none; font-weight:600; }"
                            "QPushButton:hover { background:#f25c5f; }")
        b.clicked.connect(slot)
        g.addWidget(t, 0, 0)
        g.addWidget(info, 0, 1)
        g.addWidget(d, 1, 0)
        g.addWidget(b, 1, 1, Qt.AlignRight)
        g.setColumnStretch(0, 1)
        self.v.addWidget(card)
        self.cards[key] = info

    def refresh(self):
        n, size = translator.cache_info()
        self.cards["cache_tr"].setText(f"{n} teks · {DS.human(size)}" if n else "Kosong")
        cp = DS.cache_paths(self.project, self.settings)
        tot = [DS.size_of(p) for p in cp]
        b, c = sum(x[0] for x in tot), sum(x[1] for x in tot)
        self.cards["cache"].setText(f"{DS.human(b)} ({c} file)" if c else "Kosong")
        mp = DS.model_paths()
        tot = [DS.size_of(p) for _, p in mp]
        b, c = sum(x[0] for x in tot), sum(x[1] for x in tot)
        self.cards["models"].setText(f"{DS.human(b)} ({len(mp)} model)" if mp else "Belum ada")
        self.cards["shortcuts"].setText("Default" if (self.sc_panel is None or self.sc_panel.is_default())
                                        else "Diubah")
        self.cards["reset"].setText("Factory reset")

    def _done(self, failed, what):
        if failed:
            QMessageBox.warning(self, "Data", f"Sebagian {what} tidak bisa dihapus karena sedang dipakai.\n"
                                              "Tutup lalu buka lagi aplikasi, kemudian coba lagi.")
        self.refresh()

    def _ask(self, text) -> bool:
        from .alert import ask
        return ask(self, "Data", text, yes="Hapus", no="Batal", kind="warn", danger=True)

    def _clear_tr(self):
        if self._ask("Hapus semua terjemahan yang tersimpan di cache?"):
            translator.clear_cache()
            self.refresh()

    def _clear_cache(self):
        if self._ask("Hapus cache gambar & data proses?\nHasil terjemahan (folder translated) tidak dihapus."):
            self._done(DS.clear_cache(self.project, self.settings), "cache")

    def _clear_models(self):
        if self._ask("Hapus model AI yang diunduh?\nModel akan diunduh lagi (butuh internet) saat OCR / hapus "
                     "teks AI dipakai berikutnya."):
            self._done(DS.clear_models(), "model")

    def _reset_shortcuts(self):
        if self.sc_panel:
            self.sc_panel.reset_defaults()
        self.refresh()

    def _factory_reset(self):
        if not self._ask("Reset aplikasi ke pengaturan awal?\n\nYang dihapus: semua pengaturan (termasuk API key), "
                         "cache terjemahan, shortcut, unduhan update, log.\nYang tetap: font yang diinstal, model AI, "
                         "proyek & hasil terjemahanmu."):
            return
        failed = DS.factory_reset()
        if failed:
            QMessageBox.warning(self, "Data", "Sebagian data tidak bisa dihapus:\n" + "\n".join(failed[:5]))
        if self.on_factory_reset:
            self.on_factory_reset()
