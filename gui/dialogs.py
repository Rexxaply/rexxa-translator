"""Dialog Pengaturan dan Glosarium."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase

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


SAMPLE = "KIRA-KIRA KAYAK GINI DEH!"


class FontPanel(QWidget):
    """Tab Font: instal font sendiri (.ttf/.otf/.ttc), lihat pratinjau, jadikan default, hapus.
    Font disalin ke folder data pribadi, jadi tetap ada walau aplikasi di-update."""

    def __init__(self, current_default: str, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._default = current_default or ""
        v = QVBoxLayout(self)

        v.addWidget(QLabel("<b>Font default</b>"))
        self.combo = QComboBox()
        self.combo.setToolTip("Font yang dipakai untuk semua balon (bisa diganti per balon di panel Tipografi)")
        v.addWidget(self.combo)
        self.auto_hint = QLabel()
        self.auto_hint.setWordWrap(True)
        self.auto_hint.setStyleSheet("color:#8a8e9a;")
        v.addWidget(self.auto_hint)

        v.addSpacing(6)
        v.addWidget(QLabel("<b>Font yang kamu instal</b>  <span style='color:#8a8e9a'>"
                           "— seret file font ke sini, atau klik Instal font</span>"))
        self.list = QListWidget()
        self.list.setMinimumHeight(170)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.itemDoubleClicked.connect(lambda *_: self._make_default())
        v.addWidget(self.list, 1)

        row = QHBoxLayout()
        b_add = QPushButton("+  Instal font…")
        b_add.setStyleSheet("QPushButton { background:#ff4d6d; color:white; font-weight:600; border:none; }"
                            "QPushButton:hover { background:#ff6680; }")
        b_add.clicked.connect(self._install_dialog)
        self.b_def = QPushButton("Jadikan default")
        self.b_def.clicked.connect(self._make_default)
        self.b_del = QPushButton("Hapus")
        self.b_del.clicked.connect(self._remove)
        b_dir = QPushButton("Buka folder")
        b_dir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(typeset.fonts_dir()))))
        for b in (b_add, self.b_def, self.b_del):
            row.addWidget(b)
        row.addStretch()
        row.addWidget(b_dir)
        v.addLayout(row)
        note = QLabel("Font disimpan di folder data pribadimu dan tidak pernah diunggah ke mana pun.")
        note.setStyleSheet("color:#8a8e9a; font-size:8.5pt;")
        v.addWidget(note)

        self.list.itemSelectionChanged.connect(self._update_buttons)
        self._reload()

    # ------------------------------------------------------------ data
    def default_font(self) -> str:
        return self.combo.currentData() or ""

    def _reload(self, select=None):
        win = typeset.windows_comic_fonts()
        auto = typeset.default_font("id")
        self.auto_hint.setText(
            "<small>(otomatis) sekarang memakai: <b>" + (typeset.font_name(auto) if auto else "font bawaan") + "</b>."
            + (" Terdeteksi di Windows: " + ", ".join(sorted({typeset.font_name(f) for f in win})) + "." if win else
               " Wild Words / Anime Ace yang terpasang di Windows atau diinstal di sini otomatis diutamakan.")
            + "</small>")

        cur = self.combo.currentData() if self.combo.count() else self._default
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("(otomatis) — font komik terbaik yang tersedia", "")
        for f in typeset.list_fonts():
            self.combo.addItem(typeset.font_name(f) + "   ·   " + Path(f).name, f)
        i = self.combo.findData(cur)
        self.combo.setCurrentIndex(max(0, i))
        self.combo.blockSignals(False)

        self.list.clear()
        for f in typeset.user_fonts():
            it = QListWidgetItem(f"{'★  ' if f == self.default_font() else ''}{typeset.font_name(f)}\n{SAMPLE}")
            it.setData(Qt.UserRole, f)
            it.setToolTip(f)
            fam = _qt_family(f)
            if fam:
                qf = QFont(fam)
                qf.setPointSize(12)
                it.setFont(qf)
            self.list.addItem(it)
            if select and f in select:
                it.setSelected(True)
        if not self.list.count():
            it = QListWidgetItem("Belum ada font yang diinstal.")
            it.setFlags(Qt.NoItemFlags)
            self.list.addItem(it)
        self._update_buttons()

    def _selected(self):
        return [it.data(Qt.UserRole) for it in self.list.selectedItems() if it.data(Qt.UserRole)]

    def _update_buttons(self):
        sel = self._selected()
        self.b_def.setEnabled(len(sel) == 1)
        self.b_del.setEnabled(bool(sel))

    # ------------------------------------------------------------ aksi
    def install(self, files):
        done, errors = [], []
        for f in files:
            try:
                done.append(typeset.install_font(f))
            except typeset.FontError as e:
                errors.append(str(e))
        self._reload(select=done)
        if errors:
            QMessageBox.warning(self, "Instal font", "Sebagian font gagal diinstal:\n\n" + "\n".join(errors))
        elif len(done) == 1:
            r = QMessageBox.question(self, "Instal font",
                                     f"Terinstal: {typeset.font_name(done[0])}\n\nJadikan font default sekarang?")
            if r == QMessageBox.Yes:
                self._set_default(done[0])
        elif done:
            QMessageBox.information(self, "Instal font",
                                    "Terinstal:\n" + "\n".join(typeset.font_name(d) for d in done))

    def _install_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Pilih file font", "", "Font (*.ttf *.otf *.ttc)")
        if files:
            self.install(files)

    def _set_default(self, path):
        i = self.combo.findData(path)
        if i >= 0:
            self.combo.setCurrentIndex(i)
        self._reload(select=[path])

    def _make_default(self):
        sel = self._selected()
        if len(sel) == 1:
            self._set_default(sel[0])

    def _remove(self):
        sel = self._selected()
        if not sel:
            return
        names = "\n".join(typeset.font_name(f) for f in sel)
        if QMessageBox.question(self, "Hapus font", f"Hapus font ini dari aplikasi?\n\n{names}") != QMessageBox.Yes:
            return
        if self.default_font() in sel:
            self.combo.setCurrentIndex(0)
        for f in sel:
            _qt_unload(f)
            try:
                typeset.remove_font(f)
            except (typeset.FontError, OSError) as e:
                QMessageBox.warning(self, "Hapus font", str(e))
        self._reload()

    # ------------------------------------------------------------ seret & lepas file font
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith(typeset.FONT_EXT)
                                          for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile().lower().endswith(typeset.FONT_EXT)]
        if files:
            self.install(files)


_qt_fonts: dict = {}


def _qt_family(path):
    """Daftarkan font ke Qt (hanya untuk pratinjau di daftar)."""
    if path not in _qt_fonts:
        fid = QFontDatabase.addApplicationFont(path)
        fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        _qt_fonts[path] = (fid, fams[0] if fams else "")
    return _qt_fonts[path][1]


def _qt_unload(path):
    fid, _ = _qt_fonts.pop(path, (-1, ""))
    if fid >= 0:
        QFontDatabase.removeApplicationFont(fid)


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pengaturan")
        self.resize(600, 520)
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
        self.maxsize = QSpinBox(); self.maxsize.setRange(8, 200); self.maxsize.setValue(int(self.s["max_font_size"]))
        f.addRow("Ukuran font maks", self.maxsize)
        self.stroke = QSpinBox(); self.stroke.setRange(0, 10); self.stroke.setValue(int(self.s["default_stroke"]))
        f.addRow("Stroke default", self.stroke)
        self.upper = QCheckBox("HURUF KAPITAL semua"); self.upper.setChecked(self.s.get("uppercase", True)); f.addRow("", self.upper)
        self.ital = QCheckBox("Huruf miring (italic) — gaya scanlation"); self.ital.setChecked(self.s.get("italic", True)); f.addRow("", self.ital)
        self.fmt = QComboBox(); self.fmt.addItems(["png", "jpg", "webp"]); self.fmt.setCurrentText(self.s["output_format"])
        f.addRow("Format output", self.fmt)
        row2 = QHBoxLayout()
        self.outdir = QLineEdit(self.s["output_dir"]); self.outdir.setPlaceholderText("kosong = <folder gambar>/translated")
        b2 = QPushButton("…"); b2.setFixedWidth(30); b2.clicked.connect(self._pick_out)
        row2.addWidget(self.outdir, 1); row2.addWidget(b2)
        f.addRow("Folder output", row2)
        tabs.addTab(w, "Typeset & Output")

        # --- Font
        self.fonts = FontPanel(self.s.get("font", ""))
        tabs.addTab(self.fonts, "Font")

        # --- Tentang (update selalu otomatis dari GitHub, tidak perlu diatur)
        w = QWidget(); f = QFormLayout(w)
        f.addRow("Versi", QLabel(f"<b>Rexxa Translator {version.__version__}</b>"))
        f.addRow("Update", QLabel("Otomatis — dicek saat aplikasi dibuka"))
        f.addRow(QLabel("<b>Data pribadi</b> (pengaturan, API key, font) — aman saat update:"))
        drow = QHBoxLayout()
        dl = QLineEdit(str(paths.data_dir())); dl.setReadOnly(True)
        ob = QPushButton("Buka folder")
        ob.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.data_dir()))))
        drow.addWidget(dl, 1); drow.addWidget(ob)
        f.addRow("Folder", drow)
        tabs.addTab(w, "Tentang")

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self); lay.addWidget(tabs); lay.addWidget(bb)

    def _apply_preset(self, name):
        if name in translator.LLM_PRESETS:
            url, model = translator.LLM_PRESETS[name]
            self.base.setText(url); self.model.setText(model)

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
                 font=self.fonts.default_font(),
                 max_font_size=self.maxsize.value(), default_stroke=self.stroke.value(),
                 uppercase=self.upper.isChecked(), italic=self.ital.isChecked(), output_format=self.fmt.currentText(),
                 output_dir=self.outdir.text().strip())
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
