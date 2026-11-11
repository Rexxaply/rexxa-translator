"""Dialog Pengaturan dan Glosarium."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase

from core import paths, pipeline, translator, typeset, version

from . import shortcuts as SC
from .settings_panels import DataPanel, ShortcutPanel, TextPanel
from .alert import Alert, MessageBox as QMessageBox  # noqa: E402,F811  (semua alert bergaya Rexxa)

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


class GoogleFontsDialog(QDialog):
    """Cari font di Google Fonts lalu pasang (diunduh ke folder font pribadi)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from core import gfonts
        self.gf = gfonts
        self.installed = []
        self.setWindowTitle("Google Fonts")
        self.resize(460, 520)
        v = QVBoxLayout(self)
        self.q = QLineEdit()
        self.q.setPlaceholderText("Cari nama font (mis. Bangers, Anton) atau kategori: display, handwriting…")
        v.addWidget(self.q)
        self.cats = QHBoxLayout()
        for label, key in (("Komik / kuas", "_brush"), ("Tebal", "_bold"), ("Display", "display"),
                           ("Tulisan tangan", "handwriting"), ("Semua", "")):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, k=key: self._fill(k))
            self.cats.addWidget(b)
        v.addLayout(self.cats)
        self.lst = QListWidget()
        self.lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
        v.addWidget(self.lst, 1)
        self.info = QLabel("Memuat katalog…")
        self.info.setStyleSheet("color:#8b93ab;")
        v.addWidget(self.info)
        row = QHBoxLayout()
        self.b_inst = QPushButton("Pasang yang dipilih")
        self.b_inst.setStyleSheet("QPushButton { background:#7c6cff; color:white; font-weight:600; border:none; }")
        self.b_inst.clicked.connect(self._install)
        close = QPushButton("Tutup")
        close.clicked.connect(self.accept)
        row.addStretch()
        row.addWidget(self.b_inst)
        row.addWidget(close)
        v.addLayout(row)
        self.q.textChanged.connect(lambda t: self._fill(t))
        QTimer.singleShot(50, lambda: self._fill("_brush"))

    def _fill(self, q):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if q == "_brush":
                items = [{"family": n, "category": "Komik / kuas"} for n in self.gf.BRUSH + self.gf.COMIC]
            elif q == "_bold":
                items = [{"family": n, "category": "Tebal"} for n in self.gf.SANS_BOLD]
            else:
                items = self.gf.search(q, 120)
        finally:
            QApplication.restoreOverrideCursor()
        self.lst.clear()
        seen = set()
        for c in items:
            if c["family"] in seen:
                continue
            seen.add(c["family"])
            it = QListWidgetItem(f"{c['family']}    ·  {c.get('category', '')}")
            it.setData(Qt.UserRole, c["family"])
            self.lst.addItem(it)
        self.info.setText(f"{self.lst.count()} font. Pilih satu atau beberapa, lalu Pasang.")

    def _install(self):
        fams = [it.data(Qt.UserRole) for it in self.lst.selectedItems()]
        if not fams:
            return
        cat = {c["family"]: c for c in self.gf.catalog()}
        QApplication.setOverrideCursor(Qt.WaitCursor)
        ok, bad = [], []
        try:
            for fam in fams:
                self.info.setText(f"Mengunduh {fam}…")
                QApplication.processEvents()
                weights = (cat.get(fam) or {}).get("weights") or [400, 700]
                paths_ = []
                for w in sorted({_n for _n in (400, 700, 900) if _n in weights} or {weights[0]}):
                    pth = self.gf.download(fam, w, weights)
                    if pth:
                        paths_.append(pth)
                if not paths_:
                    bad.append(fam)
                    continue
                for pth in paths_:
                    try:
                        self.installed.append(typeset.install_font(pth))
                    except Exception:
                        pass
                ok.append(fam)
        finally:
            QApplication.restoreOverrideCursor()
        msg = (f"Terpasang: {', '.join(ok)}." if ok else "") + (f"  Gagal (cek internet): {', '.join(bad)}." if bad else "")
        self.info.setText(msg.strip())


class FontPanel(QWidget):
    """Tab Font: instal font sendiri (.ttf/.otf/.ttc), lihat pratinjau, jadikan default, hapus.
    Font disalin ke folder data pribadi, jadi tetap ada walau aplikasi di-update."""

    def __init__(self, get_default, set_default, on_changed=None, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._get_default, self._set_default_cb, self._on_changed = get_default, set_default, on_changed
        v = QVBoxLayout(self)

        v.addWidget(QLabel("<b>Font default</b> diatur di tab <b>Teks</b> → Preset 1."))
        self.auto_hint = QLabel()
        self.auto_hint.setWordWrap(True)
        self.auto_hint.setStyleSheet("color:#8b93ab;")
        v.addWidget(self.auto_hint)

        v.addSpacing(6)
        v.addWidget(QLabel("<b>Font yang kamu instal</b>  <span style='color:#8b93ab'>"
                           "— seret file font ke sini, atau klik Instal font</span>"))
        self.list = QListWidget()
        self.list.setMinimumHeight(170)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.itemDoubleClicked.connect(lambda *_: self._make_default())
        v.addWidget(self.list, 1)

        row = QHBoxLayout()
        b_add = QPushButton("+  Instal font…")
        b_add.setStyleSheet("QPushButton { background:#7c6cff; color:white; font-weight:600; border:none; }"
                            "QPushButton:hover { background:#9182ff; }")
        b_add.clicked.connect(self._install_dialog)
        self.b_def = QPushButton("Jadikan default")
        self.b_def.clicked.connect(self._make_default)
        self.b_del = QPushButton("Hapus")
        self.b_del.clicked.connect(self._remove)
        b_gf = QPushButton("Google Fonts…")
        b_gf.setToolTip("Cari & pasang font gratis dari Google Fonts (perlu internet)")
        b_gf.clicked.connect(self._google_fonts)
        b_dir = QPushButton("Buka folder")
        b_dir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(typeset.fonts_dir()))))
        for b in (b_add, b_gf, self.b_def, self.b_del):
            row.addWidget(b)
        row.addStretch()
        row.addWidget(b_dir)
        v.addLayout(row)
        note = QLabel("Font disimpan di folder data pribadimu dan tidak pernah diunggah ke mana pun.")
        note.setStyleSheet("color:#8b93ab; font-size:8.5pt;")
        v.addWidget(note)

        self.list.itemSelectionChanged.connect(self._update_buttons)
        self._reload()

    def _google_fonts(self):
        d = GoogleFontsDialog(self)
        if d.exec() and d.installed:
            self._reload(select=d.installed)

    # ------------------------------------------------------------ data
    def default_font(self) -> str:
        return self._get_default() or ""

    def _reload(self, select=None):
        if self._on_changed:
            self._on_changed()
        win = typeset.windows_comic_fonts()
        auto = typeset.default_font("id")
        self.auto_hint.setText(
            "<small>(otomatis) sekarang memakai: <b>" + (typeset.font_name(auto) if auto else "font bawaan") + "</b>."
            + (" Terdeteksi di Windows: " + ", ".join(sorted({typeset.font_name(f) for f in win})) + "." if win else
               " Wild Words / Anime Ace yang terpasang di Windows atau diinstal di sini otomatis diutamakan.")
            + "</small>")

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
            from .alert import ask
            if ask(self, "Instal font", f"Font terinstal: {typeset.font_name(done[0])}\nJadikan font default sekarang?",
                   yes="Jadikan default", no="Nanti", kind="success"):
                self._set_default(done[0])
        elif done:
            QMessageBox.information(self, "Instal font",
                                    "Terinstal:\n" + "\n".join(typeset.font_name(d) for d in done))

    def _install_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Pilih file font", "", "Font (*.ttf *.otf *.ttc)")
        if files:
            self.install(files)

    def _set_default(self, path):
        self._set_default_cb(path)
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
        from .alert import ask
        if not ask(self, "Hapus font", f"Hapus font ini dari aplikasi?\n{names}", yes="Hapus", no="Batal",
                   kind="warn", danger=True):
            return
        if self.default_font() in sel:
            self._set_default_cb("")
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
    def __init__(self, settings: dict, parent=None, project=None):
        super().__init__(parent)
        self.setWindowTitle("Pengaturan")
        self.resize(640, 560)
        self.s = dict(settings)
        self.factory_reset = False
        tabs = QTabWidget()

        # --- Proses
        w = QWidget(); f = QFormLayout(w)
        self.detect = _combo(DETECT, self.s["detect_mode"]); f.addRow("Deteksi teks", self.detect)
        self.ocr = _combo(OCR, self.s["ocr_engine"]); f.addRow("Engine OCR", self.ocr)
        self.clean = _combo(CLEAN, self.s["clean_method"]); f.addRow("Hapus teks", self.clean)
        self.autopatch = QCheckBox("Perapian otomatis: area bekas teks yang belum mulus ditambal area serupa (Patch)")
        self.autopatch.setChecked(bool(self.s.get("auto_patch", True))); f.addRow("", self.autopatch)
        self.autolines = QCheckBox("Sambung otomatis garis balon yang terputus setelah teks dihapus")
        self.autolines.setChecked(bool(self.s.get("auto_lines", True))); f.addRow("", self.autolines)
        self.gpu = QCheckBox("Pakai GPU (CUDA) jika tersedia"); self.gpu.setChecked(self.s["gpu"]); f.addRow("", self.gpu)
        self.sfxmatch = QCheckBox("Teks spesial / SFX: pilih font yang mirip dengan aslinya")
        self.sfxmatch.setChecked(bool(self.s.get("sfx_font_match", True))); f.addRow("", self.sfxmatch)
        self.sysfont = QCheckBox("Boleh memakai font perangkat (Windows\\Fonts) bila lebih mirip")
        self.sysfont.setChecked(bool(self.s.get("font_match_system", True))); f.addRow("", self.sysfont)
        self.gfont = QCheckBox("Cadangan: cari di Google Fonts bila font di perangkat kurang mirip (perlu internet)")
        self.gfont.setChecked(bool(self.s.get("font_match_online", True))); f.addRow("", self.gfont)
        self.fontall = QCheckBox("Semua teks: pilih font yang mirip dengan aslinya && ingat untuk halaman berikutnya")
        self.fontall.setChecked(bool(self.s.get("font_match_all", True))); f.addRow("", self.fontall)
        from core import perf
        self.perf = QComboBox()
        for k, label in (("auto", f"Otomatis ({perf.describe(self.s)})"),
                         ("hemat", "Hemat — untuk PC/laptop spesifikasi rendah (lebih stabil)"),
                         ("normal", "Normal — pakai tenaga penuh")):
            self.perf.addItem(label, k)
        self.perf.setCurrentIndex(max(0, self.perf.findData(self.s.get("perf_mode", "auto"))))
        f.addRow("Performa", self.perf)
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
        self.extra = QTextEdit(self.s["llm_extra_prompt"]); self.extra.setFixedHeight(110)
        self.extra.setPlaceholderText("Instruksi tambahan, mis. 'Pakai bahasa gaul Jakarta untuk karakter remaja'.\n"
                                      "Boleh juga system prompt utuh ('You are…'); {targetLanguage} / {sourceLanguage} diisi otomatis.")
        self.extra.setToolTip("Instruksi ini diberi prioritas tertinggi. Prompt panjang / persona dipakai sebagai "
                              "system prompt utama; format jawaban JSON tetap diatur aplikasi.")
        f.addRow("Instruksi tambahan", self.extra)
        from core import skills
        f.addRow(QLabel("<b>Skill AI</b> <small>(untuk LLM)</small>"))
        self.style = _combo([(v[0], k) for k, v in skills.STYLES.items()], self.s.get("tl_style", "alami"))
        f.addRow("Gaya bahasa", self.style)
        self.honor = _combo([(v[0], k) for k, v in skills.HONORIFICS.items()], self.s.get("tl_honorific", "keep"))
        f.addRow("Honorifik", self.honor)
        self.memory = QCheckBox("Pakai memori cerita (tokoh, gender, panggilan)")
        self.memory.setChecked(bool(self.s.get("story_memory", True)))
        f.addRow("", self.memory)
        self.prevctx = QCheckBox("Sertakan akhir halaman sebelumnya sebagai konteks")
        self.prevctx.setChecked(bool(self.s.get("story_context", True)))
        f.addRow("", self.prevctx)
        tabs.addTab(w, "Terjemahan")

        # --- Typeset & output
        w = QWidget(); f = QFormLayout(w)
        self.maxsize = QSpinBox(); self.maxsize.setRange(8, 200); self.maxsize.setValue(int(self.s["max_font_size"]))
        f.addRow("Ukuran font maks", self.maxsize)
        self.stroke = QSpinBox(); self.stroke.setRange(0, 10); self.stroke.setValue(int(self.s["default_stroke"]))
        f.addRow("Stroke default", self.stroke)
        f.addRow("", QLabel("<small>Font, tebal, miring & KAPITAL diatur di tab <b>Teks</b> (preset).</small>"))
        self.fmt = QComboBox(); self.fmt.addItems(["png", "jpg", "webp"]); self.fmt.setCurrentText(self.s["output_format"])
        f.addRow("Format output", self.fmt)
        row2 = QHBoxLayout()
        self.outdir = QLineEdit(self.s["output_dir"]); self.outdir.setPlaceholderText("kosong = <folder gambar>/translated")
        b2 = QPushButton("…"); b2.setFixedWidth(30); b2.clicked.connect(self._pick_out)
        row2.addWidget(self.outdir, 1); row2.addWidget(b2)
        f.addRow("Folder output", row2)
        tabs.addTab(w, "Typeset & Output")

        # --- Teks (preset 1–5, ukuran font, penamaan file)
        self.text = TextPanel(self.s)
        tabs.addTab(self.text, "Teks")

        # --- Font
        self.fonts = FontPanel(self.text.default_font, self.text.set_default_font, self.text.refresh_fonts)
        tabs.addTab(self.fonts, "Font")

        # --- Shortcut & Data
        self.sc = ShortcutPanel(self.s)
        tabs.addTab(self.sc, "Shortcut")
        self.data = DataPanel(self.s, project, self.sc, self._on_factory_reset)
        tabs.addTab(self.data, "Data")
        tabs.currentChanged.connect(lambda i: tabs.widget(i) is self.data and self.data.refresh())

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
        bb.accepted.connect(self._ok); bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self); lay.addWidget(tabs); lay.addWidget(bb)

    def _on_factory_reset(self):
        self.factory_reset = True
        QMessageBox.information(self, "Reset aplikasi", "Pengaturan dikembalikan ke awal.")
        self.accept()

    def _ok(self):
        clash = SC.conflicts(self.sc.mapping())
        if clash:
            names = {sid: label for sid, _g, label, _d, _l in SC.SHORTCUTS}
            msg = "\n".join(f"{k.upper()}: " + ", ".join(names[i] for i in ids) for k, ids in clash)
            QMessageBox.warning(self, "Shortcut bentrok", "Satu tombol dipakai beberapa aksi:\n\n" + msg)
            return
        self.accept()

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
                 auto_patch=self.autopatch.isChecked(), auto_lines=self.autolines.isChecked(),
                 translate_engine=self.trans.currentData(), deepl_key=self.deepl.text().strip(),
                 llm_preset=self.preset.currentText(), llm_base_url=self.base.text().strip(),
                 llm_model=self.model.text().strip(), llm_api_key=self.key.text().strip(),
                 llm_temperature=self.temp.value(), llm_extra_prompt=self.extra.toPlainText().strip(),
                 tl_style=self.style.currentData(), tl_honorific=self.honor.currentData(),
                 story_memory=self.memory.isChecked(), story_context=self.prevctx.isChecked(),
                 max_font_size=self.maxsize.value(), default_stroke=self.stroke.value(),
                 output_format=self.fmt.currentText(), output_dir=self.outdir.text().strip(),
                 sfx_font_match=self.sfxmatch.isChecked(), font_match_system=self.sysfont.isChecked(),
                 font_match_online=self.gfont.isChecked(), font_match_all=self.fontall.isChecked(),
                 perf_mode=self.perf.currentData() or "auto")
        s.update(self.text.values())
        s.update(self.sc.values())
        pipeline.sync_default_style(s)
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
