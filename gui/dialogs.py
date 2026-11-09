"""Dialog Pengaturan dan Glosarium."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLineEdit,
                               QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
                               QTextEdit, QVBoxLayout, QWidget, QLabel)

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from core import paths, translator, typeset, version

DETECT = [("Balon (OpenCV, cepat)", "bubble"), ("EasyOCR (teks di mana saja)", "easyocr"),
          ("Hybrid (balon + teks bebas)", "hybrid")]
OCR = [("Otomatis", "auto"), ("manga-ocr (Jepang)", "manga-ocr"), ("EasyOCR", "easyocr")]
TRANS = [("Google Translate (gratis)", "google"), ("DeepL", "deepl"), ("LLM / AI (OpenAI, Gemini, lokal…)", "llm")]
CLEAN = [("Otomatis", "auto"), ("Isi warna balon", "fill"), ("OpenCV inpaint", "opencv"), ("LaMa AI inpaint", "lama")]


def _combo(items, value):
    c = QComboBox()
    for label, v in items:
        c.addItem(label, v)
    idx = c.findData(value)
    c.setCurrentIndex(max(0, idx))
    return c


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pengaturan")
        self.resize(560, 480)
        self.s = dict(settings)
        tabs = QTabWidget()

        # --- Proses
        w = QWidget(); f = QFormLayout(w)
        self.detect = _combo(DETECT, self.s["detect_mode"]); f.addRow("Deteksi teks", self.detect)
        self.ocr = _combo(OCR, self.s["ocr_engine"]); f.addRow("Engine OCR", self.ocr)
        self.clean = _combo(CLEAN, self.s["clean_method"]); f.addRow("Hapus teks", self.clean)
        self.gpu = QCheckBox("Pakai GPU (CUDA) jika tersedia"); self.gpu.setChecked(self.s["gpu"]); f.addRow("", self.gpu)
        tabs.addTab(w, "Proses")

        # --- Terjemahan
        w = QWidget(); f = QFormLayout(w)
        self.trans = _combo(TRANS, self.s["translate_engine"]); f.addRow("Engine", self.trans)
        self.deepl = QLineEdit(self.s["deepl_key"]); self.deepl.setEchoMode(QLineEdit.Password)
        f.addRow("API key DeepL", self.deepl)
        f.addRow(QLabel("<b>LLM (kompatibel OpenAI)</b>"))
        self.preset = QComboBox(); self.preset.addItems(list(translator.LLM_PRESETS) + ["Kustom"])
        self.preset.setCurrentText(self.s.get("llm_preset", "Gemini"))
        self.preset.currentTextChanged.connect(self._apply_preset)
        f.addRow("Preset", self.preset)
        self.base = QLineEdit(self.s["llm_base_url"]); f.addRow("Base URL", self.base)
        self.model = QLineEdit(self.s["llm_model"]); f.addRow("Model", self.model)
        self.key = QLineEdit(self.s["llm_api_key"]); self.key.setEchoMode(QLineEdit.Password)
        f.addRow("API key", self.key)
        self.temp = QDoubleSpinBox(); self.temp.setRange(0, 1.5); self.temp.setSingleStep(0.1)
        self.temp.setValue(float(self.s["llm_temperature"])); f.addRow("Temperature", self.temp)
        self.extra = QTextEdit(self.s["llm_extra_prompt"]); self.extra.setFixedHeight(70)
        self.extra.setPlaceholderText("Instruksi tambahan, mis. 'Pakai bahasa gaul Jakarta untuk karakter remaja'")
        f.addRow("Instruksi tambahan", self.extra)
        tabs.addTab(w, "Terjemahan")

        # --- Typeset & output
        w = QWidget(); f = QFormLayout(w)
        row = QHBoxLayout()
        self.font = QComboBox(); self.font.setEditable(True)
        self.font.addItem("(otomatis)", "")
        for p in typeset.list_fonts():
            self.font.addItem(Path(p).name, p)
        i = self.font.findData(self.s["font"]); self.font.setCurrentIndex(max(0, i))
        btn = QPushButton("…"); btn.setFixedWidth(30); btn.clicked.connect(self._pick_font)
        row.addWidget(self.font, 1); row.addWidget(btn)
        f.addRow("Font default", row)
        f.addRow("", QLabel(f"<small>Taruh font .ttf/.otf favorit di folder:<br>{typeset.fonts_dir()}</small>"))
        self.maxsize = QSpinBox(); self.maxsize.setRange(8, 200); self.maxsize.setValue(int(self.s["max_font_size"]))
        f.addRow("Ukuran font maks", self.maxsize)
        self.stroke = QSpinBox(); self.stroke.setRange(0, 10); self.stroke.setValue(int(self.s["default_stroke"]))
        f.addRow("Stroke default", self.stroke)
        self.upper = QCheckBox("HURUF KAPITAL semua"); self.upper.setChecked(self.s["uppercase"]); f.addRow("", self.upper)
        self.fmt = QComboBox(); self.fmt.addItems(["png", "jpg", "webp"]); self.fmt.setCurrentText(self.s["output_format"])
        f.addRow("Format output", self.fmt)
        row2 = QHBoxLayout()
        self.outdir = QLineEdit(self.s["output_dir"]); self.outdir.setPlaceholderText("kosong = <folder gambar>/translated")
        b2 = QPushButton("…"); b2.setFixedWidth(30); b2.clicked.connect(self._pick_out)
        row2.addWidget(self.outdir, 1); row2.addWidget(b2)
        f.addRow("Folder output", row2)
        tabs.addTab(w, "Typeset & Output")

        # --- Update
        w = QWidget(); f = QFormLayout(w)
        f.addRow("Versi terpasang", QLabel(f"<b>{version.__version__}</b>"))
        self.upd_src = QLineEdit(self.s.get("update_source", ""))
        self.upd_src.setPlaceholderText(f"{version.DEFAULT_REPO}  (default)")
        f.addRow("Sumber update", self.upd_src)
        self.upd_auto = QCheckBox("Cek otomatis saat aplikasi dibuka (maks. sekali sehari)")
        self.upd_auto.setChecked(bool(self.s.get("update_auto_check", True)))
        f.addRow("", self.upd_auto)
        f.addRow(QLabel("<b>Data pribadi</b> (pengaturan, API key, font) — aman saat update:"))
        drow = QHBoxLayout()
        dl = QLineEdit(str(paths.data_dir())); dl.setReadOnly(True)
        ob = QPushButton("Buka folder")
        ob.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.data_dir()))))
        drow.addWidget(dl, 1); drow.addWidget(ob)
        f.addRow("Folder", drow)
        tabs.addTab(w, "Update")

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self); lay.addWidget(tabs); lay.addWidget(bb)

    def _apply_preset(self, name):
        if name in translator.LLM_PRESETS:
            url, model = translator.LLM_PRESETS[name]
            self.base.setText(url); self.model.setText(model)

    def _pick_font(self):
        p, _ = QFileDialog.getOpenFileName(self, "Pilih font", "", "Font (*.ttf *.otf *.ttc)")
        if p:
            self.font.addItem(Path(p).name, p); self.font.setCurrentIndex(self.font.count() - 1)

    def _pick_out(self):
        d = QFileDialog.getExistingDirectory(self, "Folder output")
        if d:
            self.outdir.setText(d)

    def result_settings(self) -> dict:
        s = self.s
        s.update(detect_mode=self.detect.currentData(), ocr_engine=self.ocr.currentData(),
                 clean_method=self.clean.currentData(), gpu=self.gpu.isChecked(),
                 translate_engine=self.trans.currentData(), deepl_key=self.deepl.text().strip(),
                 llm_preset=self.preset.currentText(), llm_base_url=self.base.text().strip(),
                 llm_model=self.model.text().strip(), llm_api_key=self.key.text().strip(),
                 llm_temperature=self.temp.value(), llm_extra_prompt=self.extra.toPlainText().strip(),
                 font=self.font.currentData() or (self.font.currentText() if Path(self.font.currentText()).exists() else ""),
                 max_font_size=self.maxsize.value(), default_stroke=self.stroke.value(),
                 uppercase=self.upper.isChecked(), output_format=self.fmt.currentText(),
                 output_dir=self.outdir.text().strip(),
                 update_source=self.upd_src.text().strip(), update_auto_check=self.upd_auto.isChecked())
        return s


class GlossaryDialog(QDialog):
    def __init__(self, glossary: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Glosarium (istilah tetap)")
        self.resize(460, 420)
        self.t = QTableWidget(0, 2)
        self.t.setHorizontalHeaderLabels(["Istilah asli", "Terjemahan"])
        self.t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for k, v in glossary.items():
            self._add(k, v)
        add = QPushButton("+ Tambah"); add.clicked.connect(lambda: self._add("", ""))
        rm = QPushButton("Hapus baris"); rm.clicked.connect(lambda: self.t.removeRow(self.t.currentRow()))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        row = QHBoxLayout(); row.addWidget(add); row.addWidget(rm); row.addStretch()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Nama karakter, jurus, tempat — dipakai konsisten di semua halaman."))
        lay.addWidget(self.t); lay.addLayout(row); lay.addWidget(bb)

    def _add(self, k, v):
        r = self.t.rowCount(); self.t.insertRow(r)
        self.t.setItem(r, 0, QTableWidgetItem(k)); self.t.setItem(r, 1, QTableWidgetItem(v))

    def result_glossary(self) -> dict:
        out = {}
        for r in range(self.t.rowCount()):
            k = (self.t.item(r, 0).text() if self.t.item(r, 0) else "").strip()
            v = (self.t.item(r, 1).text() if self.t.item(r, 1) else "").strip()
            if k:
                out[k] = v
        return out
