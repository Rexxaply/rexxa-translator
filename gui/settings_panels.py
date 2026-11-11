"""Tab Pengaturan: Teks (preset), Shortcut, Data."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QKeySequenceEdit, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSpinBox,
                               QToolButton, QVBoxLayout, QWidget)

from core import datastore as DS
from core import pipeline, translator, typeset
from . import shortcuts as SC
from .alert import Alert, MessageBox as QMessageBox  # noqa: E402,F811  (semua alert bergaya Rexxa)

DIM = "color:#8b93ab;"


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
            lbl = QLabel(f"Preset {n}" + ("  <span style='color:#7c6cff'>default</span>" if n == 1 else ""))
            from .fontcombo import FontCombo
            font = FontCombo()
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
                title.setStyleSheet("font-weight:600; font-size:8.5pt; color:#c8cede;")
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
        self._work_card()
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

    # ---------------------------------------------------------------- folder kerja per chapter
    def _work_card(self):
        card = QFrame()
        card.setObjectName("card")
        v = QVBoxLayout(card)
        top = QHBoxLayout()
        t = QLabel("Hasil kerja per chapter")
        t.setStyleSheet("font-weight:600;")
        self.work_total = QLabel("")
        self.work_total.setStyleSheet("font-weight:600;")
        top.addWidget(t, 1)
        top.addWidget(self.work_total)
        v.addLayout(top)
        d = QLabel("Gambar jadi & gambar bersih tiap chapter (folder tersembunyi aplikasi). Dipakai saat proyek "
                   "dibuka lagi untuk diedit / di-export ulang. Kalau dihapus, halaman chapter itu perlu diproses "
                   "ulang. Gambar yang sudah kamu export tidak ikut terhapus.")
        d.setWordWrap(True)
        d.setStyleSheet(DIM + "font-size:8.5pt;")
        v.addWidget(d)
        self.work_list = QListWidget()
        self.work_list.setMinimumHeight(150)
        self.work_list.setStyleSheet(
            "QListWidget::indicator { width:14px; height:14px; border:1.5px solid #8a93b3; border-radius:4px; "
            "background:#1c2130; } QListWidget::indicator:checked { background:#7c6cff; border-color:#9182ff; }")
        self.work_list.itemChanged.connect(lambda *_: self._work_sel_changed())
        v.addWidget(self.work_list)
        row = QHBoxLayout()
        self.work_all = QPushButton("Centang semua")
        self.work_all.clicked.connect(self._work_toggle_all)
        self.work_del = QPushButton("Hapus yang dicentang")
        self.work_del.setStyleSheet("QPushButton:enabled { background:#e5383b; color:white; border:none; "
                                    "font-weight:600; } QPushButton:enabled:hover { background:#f25c5f; }")
        self.work_del.clicked.connect(self._work_delete)
        row.addWidget(self.work_all)
        row.addStretch()
        row.addWidget(self.work_del)
        v.addLayout(row)
        auto = QHBoxLayout()
        auto.addWidget(QLabel("Hapus otomatis bila tidak dibuka lebih dari"))
        self.work_days = QSpinBox()
        self.work_days.setRange(0, 365)
        self.work_days.setSpecialValueText("tidak pernah")
        self.work_days.setSuffix(" hari")
        self.work_days.setValue(int(self.settings.get("work_keep_days", 30) or 0))
        self.work_days.valueChanged.connect(lambda n: self.settings.__setitem__("work_keep_days", int(n)))
        auto.addWidget(self.work_days)
        auto.addStretch()
        v.addLayout(auto)
        n = QLabel("Dicek setiap aplikasi dibuka. Chapter yang sedang terbuka tidak pernah dihapus otomatis.")
        n.setWordWrap(True)
        n.setStyleSheet(DIM + "font-size:8.5pt;")
        v.addWidget(n)
        self.v.addWidget(card)

    def _fill_work(self):
        import time
        self.work_list.blockSignals(True)
        self.work_list.clear()
        cur = DS.project_work_dirs(self.project, self.settings)
        items = DS.work_dirs()
        total = 0
        for w in items:
            total += w["bytes"]
            days = int((time.time() - w["used"]) // 86400) if w["used"] else 0
            when = "hari ini" if days <= 0 else ("kemarin" if days == 1 else f"{days} hari lalu")
            open_now = Path(w["path"]).resolve() in cur
            label = (f"{w['series'] + ' › ' if w['series'] else ''}{w['name']}\n"
                     f"{DS.human(w['bytes'])} · {w['files']} file · dibuka {when}"
                     + ("  · sedang terbuka" if open_now else ""))
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, str(w["path"]))
            it.setToolTip(w["source"] or str(w["path"]))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            self.work_list.addItem(it)
        if not items:
            it = QListWidgetItem("Belum ada hasil kerja tersimpan.")
            it.setFlags(Qt.NoItemFlags)
            self.work_list.addItem(it)
        self.work_list.blockSignals(False)
        self.work_total.setText(f"{DS.human(total)} · {len(items)} chapter" if items else "Kosong")
        self._work_sel_changed()

    def _work_checked(self):
        return [self.work_list.item(i) for i in range(self.work_list.count())
                if self.work_list.item(i).data(Qt.UserRole) and
                self.work_list.item(i).checkState() == Qt.Checked]

    def _work_sel_changed(self):
        n = len(self._work_checked())
        self.work_del.setEnabled(n > 0)
        self.work_del.setText(f"Hapus {n} chapter" if n else "Hapus yang dicentang")
        anyitems = any(self.work_list.item(i).data(Qt.UserRole) for i in range(self.work_list.count()))
        self.work_all.setEnabled(anyitems)

    def _work_toggle_all(self):
        rows = [self.work_list.item(i) for i in range(self.work_list.count()) if self.work_list.item(i).data(Qt.UserRole)]
        on = not all(r.checkState() == Qt.Checked for r in rows)
        self.work_list.blockSignals(True)
        for r in rows:
            r.setCheckState(Qt.Checked if on else Qt.Unchecked)
        self.work_list.blockSignals(False)
        self.work_all.setText("Hapus centang" if on else "Centang semua")
        self._work_sel_changed()

    def _work_delete(self):
        sel = self._work_checked()
        if not sel:
            return
        cur = DS.project_work_dirs(self.project, self.settings)
        busy = [s for s in sel if Path(s.data(Qt.UserRole)).resolve() in cur]
        msg = f"Hapus hasil kerja {len(sel)} chapter?\nHalaman chapter itu perlu diproses ulang bila dibuka lagi."
        if busy:
            msg += "\n\nTermasuk chapter yang sedang terbuka — halamannya akan diproses ulang saat dirender."
        if not self._ask(msg):
            return
        failed = DS.delete_work([s.data(Qt.UserRole) for s in sel])
        if busy and self.project is not None:
            for pg in self.project.pages:
                for attr in ("cleaned_path", "output_path"):
                    if getattr(pg, attr, "") and not Path(getattr(pg, attr)).exists():
                        setattr(pg, attr, "")
        self._done(failed, "hasil kerja")

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
        self._fill_work()
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
        if self._ask("Hapus cache gambar & data proses?\nHasil terjemahan di folder kerja tidak dihapus."):
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
