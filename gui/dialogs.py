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
from .glass import GlassDialog
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


# ====================================================================== Pengaturan (Liquid Glass)
SETTINGS_STYLE = """
QListWidget#gNav { background: transparent; border: none; outline: none; font-weight: 600; font-size: 9.5pt; }
QListWidget#gNav::item { height: 36px; padding-left: 8px; border-radius: 12px; color: rgba(225,229,242,0.70); margin: 1px 0; }
QListWidget#gNav::item:hover { background: rgba(255,255,255,0.06); color: #f2f4fb; }
QListWidget#gNav::item:selected { color: #ffffff;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,0.20), stop:1 rgba(255,255,255,0.07));
    border: 1px solid rgba(255,255,255,0.16); }
QFrame#gCard { background: rgba(255,255,255,0.035); border: 1px solid rgba(255,255,255,0.075); border-radius: 16px; }
QFrame#gCard QLabel { background: transparent; }
QLabel#gPageTitle { font-family: 'Plus Jakarta Sans', 'Inter', sans-serif; font-size: 15pt; font-weight: 800; color: #f2f4fb; }
QLabel#gPageDesc { color: rgba(225,229,242,0.58); font-size: 9pt; }
QLabel#gCardTitle { font-family: 'Plus Jakarta Sans', 'Inter', sans-serif; font-size: 10.5pt; font-weight: 700; color: #eef0f7; }
QLabel#gCardDesc { color: rgba(225,229,242,0.52); font-size: 8.5pt; }
QLabel#gLabel { color: #dfe3ef; }
QLabel#gHint { color: rgba(200,206,230,0.55); font-size: 10pt; }
QLabel#gHint:hover { color: #b9adff; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {
    background: rgba(0,0,0,0.26); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 5px 9px;
    min-height: 22px; color: #eef0f7; selection-background-color: #6f7fe0; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus { border: 1px solid rgba(170,160,255,0.75); }
QPushButton#gSmall { min-height: 28px; padding: 0 12px; border-radius: 14px; color: #e3e7f3; font-weight: 600;
    border: 1px solid rgba(255,255,255,0.10);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,0.11), stop:1 rgba(255,255,255,0.04)); }
QPushButton#gSmall:hover { background: rgba(255,255,255,0.15); }
QPushButton#gSmall:disabled { color: rgba(225,229,242,0.30); }
QPushButton#gDanger { min-height: 28px; padding: 0 12px; border-radius: 14px; font-weight: 600; color: #ff9aa4;
    border: 1px solid rgba(255,110,125,0.35); background: rgba(255,110,125,0.08); }
QPushButton#gDanger:hover { background: rgba(255,110,125,0.18); }
QPushButton#gDanger:disabled { color: rgba(255,154,164,0.30); border-color: rgba(255,110,125,0.12); }
QCheckBox { color: #dfe3ef; spacing: 8px; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 1px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.18); border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.32); }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { background: none; height: 0; }
"""

# penjelasan yang muncul saat kursor diarahkan ke pengaturan
TIPS = {
    "detect": "Cara aplikasi menemukan teks di halaman.\n• Balon: cepat, untuk teks di dalam balon kata.\n"
              "• EasyOCR: menemukan teks di mana saja (narasi, papan, SFX), lebih lambat.\n• Hybrid: gabungan keduanya.",
    "ocr": "Mesin pembaca teks asli. manga-ocr paling akurat untuk Jepang; EasyOCR untuk Korea, Mandarin, Inggris.\n"
           "Otomatis = dipilih sesuai bahasa sumber.",
    "clean": "Cara menghapus teks asli dari gambar.\n• Isi warna balon: tercepat, untuk balon polos.\n"
             "• OpenCV inpaint: cepat untuk latar sederhana.\n• LaMa AI: paling rapi untuk latar bergambar, lebih lambat.",
    "autopatch": "Bekas teks yang masih belum mulus ditambal otomatis dengan potongan area yang mirip di sekitarnya.",
    "autolines": "Garis tepi balon yang ikut terhapus disambung lagi secara otomatis.",
    "gpu": "Pakai kartu grafis NVIDIA (CUDA) untuk OCR & LaMa supaya jauh lebih cepat. Tidak berpengaruh bila tidak ada GPU.",
    "perf": "Hemat = memakai lebih sedikit memori & thread (lebih stabil di laptop spesifikasi rendah).\n"
            "Normal = tenaga penuh. Otomatis = dipilih dari spesifikasi PC-mu.",
    "sfx": "Untuk teks spesial / SFX, aplikasi mencari font yang bentuknya mirip dengan tulisan aslinya.",
    "sysfont": "Font yang terpasang di Windows boleh dipakai bila bentuknya lebih mirip dengan teks asli.",
    "gfont": "Bila font di perangkat kurang mirip, aplikasi mencari cadangan di Google Fonts (perlu internet).",
    "fontall": "Setiap jenis teks (dialog, narasi, teriakan…) diberi font yang mirip aslinya, dan pilihanmu diingat untuk "
               "halaman berikutnya.",
    "preset": "Simpan beberapa pengaturan engine (mis. Gemini & OpenRouter). Kalau satu sedang gangguan, tinggal pindah "
              "preset — dari sini atau dari menu panah di tombol Terjemahkan.\n+ Baru = salin pengaturan yang tampil jadi "
              "preset baru · Ganti nama · Hapus (minimal tersisa satu preset).",
    "engine": "Mesin penerjemah.\n• Google: gratis, cepat, kualitas standar.\n• DeepL: lebih natural, butuh API key.\n"
              "• LLM / AI: paling natural & bisa diatur gayanya (Gemini, OpenAI, OpenRouter, lokal…).",
    "deepl": "API key dari akun DeepL (deepl.com → Akun → API key). Disimpan hanya di komputermu.",
    "provider": "Isi otomatis alamat & model untuk penyedia populer. Pilih Kustom untuk mengisi sendiri.",
    "base": "Alamat API yang kompatibel OpenAI, mis. https://generativelanguage.googleapis.com/v1beta/openai.",
    "model": "Nama model di penyedia tersebut, mis. gemini-2.5-flash, gpt-4o-mini, claude-sonnet-5.",
    "key": "API key penyedia LLM. Disimpan hanya di komputermu, tidak pernah dikirim ke tempat lain.",
    "temp": "Kreativitas jawaban AI. 0,2–0,4 = konsisten & setia ke teks asli (disarankan). Lebih tinggi = lebih bebas.",
    "extra": "Instruksi untuk AI, prioritas tertinggi. Boleh kalimat pendek (mis. 'pakai gue/lo') atau system prompt "
             "utuh ('You are…'). {targetLanguage} / {sourceLanguage} diisi otomatis.",
    "style": "Nada bahasa hasil terjemahan: santai, gaul, baku, kocak, atau dramatis.",
    "honor": "Pertahankan panggilan asli (-san, senpai, oppa) atau ganti dengan padanan Indonesia (kak, bang, pak).",
    "memory": "AI mengingat tokoh, gender, dan cara mereka saling memanggil, supaya terjemahan konsisten antar halaman.",
    "prevctx": "Beberapa kalimat terakhir halaman sebelumnya ikut dikirim sebagai konteks percakapan.",
    "maxsize": "Batas ukuran huruf saat ukuran diatur otomatis (Auto) mengikuti besar balon.",
    "stroke": "Ketebalan garis tepi huruf untuk kotak teks baru (0 = tanpa garis tepi).",
    "fmt": "Format file hasil kerja. PNG = kualitas penuh; JPG / WebP = lebih kecil.",
    "outdir": "Tempat hasil kerja sementara (gambar jadi & bersih). Kosongkan untuk memakai folder tersembunyi aplikasi. "
              "Gambar untuk dibagikan dibuat lewat Export (Ctrl+E).",
}


class SettingsDialog(GlassDialog):
    NAV = [("Proses", "scan", "Deteksi, OCR & penghapusan teks"),
           ("Terjemahan", "translate", "Engine, preset & gaya bahasa"),
           ("Typeset & Output", "image", "Ukuran huruf & file hasil"),
           ("Teks", "type", "Preset gaya teks 1–5"),
           ("Font", "bold", "Font yang terpasang"),
           ("Shortcut", "keyboard", "Pintasan keyboard"),
           ("Data", "database", "Cache, hasil kerja & reset"),
           ("Tentang", "info", "Versi & folder data")]

    def __init__(self, settings: dict, parent=None, project=None):
        super().__init__(parent, "Pengaturan", "Arahkan kursor ke ikon (i) atau ke sebuah pengaturan untuk melihat gunanya.",
                         size=(860, 600))
        import copy
        from PySide6.QtWidgets import QStackedWidget
        from .icons import icon
        self.setStyleSheet(self.styleSheet() + SETTINGS_STYLE)
        self.s = copy.deepcopy(dict(settings))
        pipeline.ensure_engine_presets(self.s)
        self.factory_reset = False
        self._loading = False

        row = QHBoxLayout()
        row.setSpacing(14)
        self.nav = QListWidget()
        self.nav.setObjectName("gNav")
        self.nav.setFixedWidth(178)
        from PySide6.QtCore import QSize
        self.nav.setIconSize(QSize(17, 17))
        self.stack = QStackedWidget()
        for name, ico, tip in self.NAV:
            it = QListWidgetItem(icon(ico), "  " + name)
            self.nav.addItem(it)
        row.addWidget(self.nav)
        row.addWidget(self.stack, 1)
        self.body.addLayout(row, 1)

        self._build_process()
        self._build_translate()
        self._build_output()
        self.text = TextPanel(self.s)
        self._page_wrap("Teks", "Preset 1–5: font, tebal, miring & huruf kapital yang bisa dipakai cepat dengan "
                                "tombol 1–5. Preset 1 = gaya bawaan.", self.text, scroll=False)
        self.fonts = FontPanel(self.text.default_font, self.text.set_default_font, self.text.refresh_fonts)
        self._page_wrap("Font", "Instal font sendiri (.ttf / .otf), cari di Google Fonts, atau jadikan default.",
                        self.fonts, scroll=False)
        self.sc = ShortcutPanel(self.s)
        self._page_wrap("Shortcut", "Klik sebuah pintasan lalu tekan kombinasi tombol baru.", self.sc, scroll=False)
        self.data = DataPanel(self.s, project, self.sc, self._on_factory_reset)
        self._page_wrap("Data", "Ukuran cache & hasil kerja, pembersihan otomatis, dan reset aplikasi.", self.data,
                        scroll=False)
        self._build_about()

        self.nav.currentRowChanged.connect(self._go)
        self.nav.setCurrentRow(int(self.s.get("_settings_tab", 0) or 0) if 0 <= int(self.s.get("_settings_tab", 0) or 0)
                               < self.nav.count() else 0)

        hint = QLabel("Perubahan berlaku setelah Simpan.")
        hint.setObjectName("gSub")
        cancel = QPushButton("Batal")
        cancel.setObjectName("gGhost")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Simpan")
        ok.setObjectName("gPrimary")
        ok.setDefault(True)
        ok.clicked.connect(self._ok)
        self.footer.addWidget(hint)
        self.footer.addStretch()
        self.footer.addWidget(cancel)
        self.footer.addWidget(ok)
        from .glass import smooth_all
        smooth_all(self)
        self._sig0 = self._sig()                 # keadaan awal, untuk mendeteksi perubahan

    # ------------------------------------------------------------ konfirmasi sebelum menutup
    def _sig(self) -> str:
        import copy
        import json
        keep, keep_text = copy.deepcopy(self.s), self.extra.toPlainText()
        try:
            r = dict(self.result_settings())
        finally:
            self.s.clear()
            self.s.update(keep)                  # result_settings() tidak boleh mengubah apa pun di sini
        r.pop("_settings_tab", None)
        return json.dumps(r, sort_keys=True, default=str) + keep_text

    def changed(self) -> bool:
        try:
            return self._sig() != self._sig0
        except Exception:
            return False

    def reject(self):
        """Batal / × / Esc: bila ada perubahan, tanya dulu Simpan, Kembali, atau Tutup tanpa menyimpan."""
        if self._closing is None and not self.factory_reset and self.changed():
            from .alert import Alert
            choice = Alert(self, "Pengaturan", "Simpan perubahan pengaturan?",
                           "Ada pengaturan yang kamu ubah tapi belum disimpan.", kind="save",
                           buttons=[("Simpan", "primary", "save"), ("Kembali", "neutral", "back"),
                                    ("Tutup tanpa simpan", "danger", "discard")],
                           escape_value="back").exec_value()
            if choice == "save":
                self._ok()
                return
            if choice != "discard":
                return                           # Kembali: tetap di Pengaturan
        super().reject()

    # ------------------------------------------------------------ kerangka halaman
    def _go(self, i):
        self.stack.setCurrentIndex(i)
        if self.stack.widget(i) is getattr(self, "_data_page", None):
            self.data.refresh()

    def _page(self, title, desc):
        from PySide6.QtWidgets import QScrollArea
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(2, 0, 10, 8)
        v.setSpacing(12)
        t = QLabel(title)
        t.setObjectName("gPageTitle")
        d = QLabel(desc)
        d.setObjectName("gPageDesc")
        d.setWordWrap(True)
        v.addWidget(t)
        v.addWidget(d)
        sa.setWidget(inner)
        self.stack.addWidget(sa)
        return v

    def _page_wrap(self, title, desc, widget, scroll=True):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(2, 0, 4, 0)
        v.setSpacing(10)
        t = QLabel(title)
        t.setObjectName("gPageTitle")
        d = QLabel(desc)
        d.setObjectName("gPageDesc")
        d.setWordWrap(True)
        v.addWidget(t)
        v.addWidget(d)
        v.addWidget(widget, 1)
        self.stack.addWidget(w)
        if widget is getattr(self, "data", None):
            self._data_page = w

    def _card(self, parent_layout, title=None, desc=None):
        from PySide6.QtWidgets import QFrame, QGridLayout
        card = QFrame()
        card.setObjectName("gCard")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 13, 16, 14)
        outer.setSpacing(8)
        if title:
            t = QLabel(title)
            t.setObjectName("gCardTitle")
            outer.addWidget(t)
        if desc:
            d = QLabel(desc)
            d.setObjectName("gCardDesc")
            d.setWordWrap(True)
            outer.addWidget(d)
        g = QGridLayout()
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(8)
        g.setColumnStretch(1, 1)
        g.setColumnMinimumWidth(0, 128)
        outer.addLayout(g)
        parent_layout.addWidget(card)
        card.grid = g
        return card

    @staticmethod
    def _hint(tip):
        from .icons import icon
        h = QLabel()
        h.setObjectName("gHint")
        h.setPixmap(icon("info", "#9aa2c4").pixmap(16, 16))
        h.setFixedWidth(18)
        h.setToolTip(tip)
        h.setCursor(Qt.WhatsThisCursor)
        return h

    def _row(self, card, label, widget, tip_key):
        g = card.grid
        r = g.rowCount()
        tip = TIPS.get(tip_key, "")
        lab = QLabel(label)                         # keterangan hanya di ikon (i), tidak di label / kolom
        lab.setObjectName("gLabel")
        g.addWidget(lab, r, 0, Qt.AlignLeft | Qt.AlignVCenter)
        if isinstance(widget, QWidget):
            g.addWidget(widget, r, 1)
        else:
            g.addLayout(widget, r, 1)
        g.addWidget(self._hint(tip), r, 2)
        return lab

    def _check(self, card, text, checked, tip_key):
        g = card.grid
        r = g.rowCount()
        cb = QCheckBox(text)
        cb.setChecked(bool(checked))
        g.addWidget(cb, r, 0, 1, 2)
        g.addWidget(self._hint(TIPS.get(tip_key, "")), r, 2)
        return cb

    # ------------------------------------------------------------ halaman: Proses
    def _build_process(self):
        v = self._page("Proses", "Cara aplikasi menemukan, membaca, dan menghapus teks asli di halaman.")
        c = self._card(v, "Deteksi & baca teks")
        self.detect = _combo(DETECT, self.s["detect_mode"])
        self._row(c, "Deteksi teks", self.detect, "detect")
        self.ocr = _combo(OCR, self.s["ocr_engine"])
        self._row(c, "Engine OCR", self.ocr, "ocr")
        c = self._card(v, "Hapus teks asli")
        self.clean = _combo(CLEAN, self.s["clean_method"])
        self._row(c, "Metode", self.clean, "clean")
        self.autopatch = self._check(c, "Rapikan otomatis bekas teks yang belum mulus (Patch)",
                                     self.s.get("auto_patch", True), "autopatch")
        self.autolines = self._check(c, "Sambung garis balon yang ikut terhapus", self.s.get("auto_lines", True),
                                     "autolines")
        c = self._card(v, "Pencocokan font", "Memilih font hasil terjemahan yang mirip dengan tulisan aslinya.")
        self.fontall = self._check(c, "Semua teks: pilih font yang mirip && ingat untuk halaman berikutnya",
                                   self.s.get("font_match_all", True), "fontall")
        self.sfxmatch = self._check(c, "Teks spesial / SFX: cari font yang mirip", self.s.get("sfx_font_match", True),
                                    "sfx")
        self.sysfont = self._check(c, "Boleh memakai font Windows bila lebih mirip",
                                   self.s.get("font_match_system", True), "sysfont")
        self.gfont = self._check(c, "Cadangan dari Google Fonts (perlu internet)", self.s.get("font_match_online", True),
                                 "gfont")
        c = self._card(v, "Performa")
        from core import perf
        self.perf = QComboBox()
        for k, label in (("auto", f"Otomatis ({perf.describe(self.s)})"),
                         ("hemat", "Hemat — PC / laptop spesifikasi rendah"),
                         ("normal", "Normal — tenaga penuh")):
            self.perf.addItem(label, k)
        self.perf.setCurrentIndex(max(0, self.perf.findData(self.s.get("perf_mode", "auto"))))
        self._row(c, "Mode", self.perf, "perf")
        self.gpu = self._check(c, "Pakai GPU (CUDA) bila tersedia", self.s["gpu"], "gpu")
        v.addStretch()

    # ------------------------------------------------------------ halaman: Terjemahan
    def _build_translate(self):
        v = self._page("Terjemahan", "Pilih mesin penerjemah dan atur gaya bahasanya. Simpan beberapa preset engine "
                                     "supaya gampang pindah saat satu model bermasalah.")
        c = self._card(v, "Preset engine", "Setiap preset menyimpan engine, alamat, model, API key & temperature. "
                                           "Perubahan di bawah langsung tersimpan ke preset yang dipilih.")
        self.ep = QComboBox()
        self.ep.setMinimumWidth(180)
        self._row(c, "Preset aktif", self.ep, "preset")
        btns = QHBoxLayout()
        btns.setSpacing(6)
        self.ep_new = QPushButton("+ Baru")
        self.ep_new.setObjectName("gSmall")
        self.ep_ren = QPushButton("Ganti nama")
        self.ep_ren.setObjectName("gSmall")
        self.ep_del = QPushButton("Hapus")
        self.ep_del.setObjectName("gDanger")
        for b in (self.ep_new, self.ep_ren, self.ep_del):
            btns.addWidget(b)
        btns.addStretch()
        c.grid.addLayout(btns, c.grid.rowCount(), 1, 1, 2)
        self.ep_new.clicked.connect(self._ep_new)
        self.ep_ren.clicked.connect(self._ep_rename)
        self.ep_del.clicked.connect(self._ep_delete)

        c = self._card(v, "Engine")
        self.trans = _combo(TRANS, self.s["translate_engine"])
        self._row(c, "Engine", self.trans, "engine")
        self.deepl = QLineEdit(self.s["deepl_key"])
        self.deepl.setEchoMode(QLineEdit.Password)
        self.deepl.setPlaceholderText("API key DeepL")
        self.l_deepl = self._row(c, "API key DeepL", self.deepl, "deepl")
        self.preset = QComboBox()
        self.preset.addItems(list(translator.LLM_PRESETS) + ["Kustom"])
        self.preset.setCurrentText(self.s.get("llm_preset", "Gemini"))
        self.l_preset = self._row(c, "Penyedia", self.preset, "provider")
        self.base = QLineEdit(self.s["llm_base_url"])
        self.l_base = self._row(c, "Base URL", self.base, "base")
        self.model = QLineEdit(self.s["llm_model"])
        self.l_model = self._row(c, "Model", self.model, "model")
        self.key = QLineEdit(self.s["llm_api_key"])
        self.key.setEchoMode(QLineEdit.Password)
        self.l_key = self._row(c, "API key", self.key, "key")
        self.temp = QDoubleSpinBox()
        self.temp.setRange(0, 1.5)
        self.temp.setSingleStep(0.1)
        self.temp.setValue(float(self.s["llm_temperature"]))
        self.l_temp = self._row(c, "Temperature", self.temp, "temp")
        self._engine_card = c

        c = self._card(v, "Gaya terjemahan", "Berlaku untuk engine LLM / AI.")
        self.extra = QTextEdit(self.s["llm_extra_prompt"])
        self.extra.setFixedHeight(92)
        self.extra.setPlaceholderText("mis. 'Pakai bahasa gaul Jakarta untuk karakter remaja', atau system prompt utuh.")
        self._row(c, "Instruksi tambahan", self.extra, "extra")
        from core import skills
        self.style = _combo([(x[0], k) for k, x in skills.STYLES.items()], self.s.get("tl_style", "alami"))
        self._row(c, "Gaya bahasa", self.style, "style")
        self.honor = _combo([(x[0], k) for k, x in skills.HONORIFICS.items()], self.s.get("tl_honorific", "keep"))
        self._row(c, "Honorifik", self.honor, "honor")
        self.memory = self._check(c, "Pakai memori cerita (tokoh, gender, panggilan)", self.s.get("story_memory", True),
                                  "memory")
        self.prevctx = self._check(c, "Sertakan akhir halaman sebelumnya sebagai konteks",
                                   self.s.get("story_context", True), "prevctx")
        v.addStretch()

        self.preset.currentTextChanged.connect(self._apply_provider)
        for w in (self.deepl, self.base, self.model, self.key):
            w.textEdited.connect(self._ep_store)
        self.temp.valueChanged.connect(self._ep_store)
        self.trans.currentIndexChanged.connect(self._engine_changed)
        self.ep.currentIndexChanged.connect(self._ep_switch)
        self._ep_cur = self.s.get("engine_preset")
        self._ep_fill()
        self._engine_changed()

    # ------------------------------------------------------------ preset engine
    def _ep_fill(self):
        self._loading = True
        self.ep.clear()
        for p in self.s["engine_presets"]:
            self.ep.addItem(p["name"])
        self.ep.setCurrentText(self._ep_cur)
        self._loading = False
        self.ep_del.setEnabled(len(self.s["engine_presets"]) > 1)

    def _fields(self) -> dict:
        return {"translate_engine": self.trans.currentData(), "deepl_key": self.deepl.text().strip(),
                "llm_preset": self.preset.currentText(), "llm_base_url": self.base.text().strip(),
                "llm_model": self.model.text().strip(), "llm_api_key": self.key.text().strip(),
                "llm_temperature": self.temp.value()}

    def _ep_store(self, *_):
        if self._loading:
            return
        p = pipeline.find_engine_preset(self.s, self._ep_cur)
        if p is not None:
            p.update(self._fields())

    def _ep_load(self, name):
        p = pipeline.find_engine_preset(self.s, name) or {}
        self._loading = True
        self.trans.setCurrentIndex(max(0, self.trans.findData(p.get("translate_engine", "google"))))
        self.deepl.setText(p.get("deepl_key", ""))
        self.preset.setCurrentText(p.get("llm_preset", "Kustom"))
        self.base.setText(p.get("llm_base_url", ""))
        self.model.setText(p.get("llm_model", ""))
        self.key.setText(p.get("llm_api_key", ""))
        self.temp.setValue(float(p.get("llm_temperature", 0.3)))
        self._loading = False
        self._engine_changed()

    def _ep_switch(self, _i):
        if self._loading:
            return
        self._ep_store()
        self._ep_cur = self.ep.currentText()
        self._ep_load(self._ep_cur)

    def _ask_name(self, title, current=""):
        d = NameDialog(self, title, current, [p["name"] for p in self.s["engine_presets"] if p["name"] != current])
        return d.value() if d.exec() else None

    def _ep_new(self):
        self._ep_store()
        n = 2
        while pipeline.find_engine_preset(self.s, f"Preset {n}"):
            n += 1
        name = self._ask_name("Preset baru", f"Preset {n}")
        if not name:
            return
        self.s["engine_presets"].append(dict(self._fields(), name=name))
        self._ep_cur = name
        self._ep_fill()

    def _ep_rename(self):
        old = self._ep_cur
        name = self._ask_name("Ganti nama preset", old)
        if not name or name == old:
            return
        pipeline.find_engine_preset(self.s, old)["name"] = name
        self._ep_cur = name
        self._ep_fill()

    def _ep_delete(self):
        if len(self.s["engine_presets"]) <= 1:
            return
        from .alert import ask
        if not ask(self, "Hapus preset", f"Hapus preset “{self._ep_cur}”?", yes="Hapus", no="Batal", kind="warn",
                   danger=True):
            return
        self.s["engine_presets"] = [p for p in self.s["engine_presets"] if p["name"] != self._ep_cur]
        self._ep_cur = self.s["engine_presets"][0]["name"]
        self._ep_fill()
        self._ep_load(self._ep_cur)

    def _engine_changed(self, *_):
        eng = self.trans.currentData()
        for w, lab, show in ((self.deepl, self.l_deepl, eng == "deepl"),
                             (self.preset, self.l_preset, eng == "llm"), (self.base, self.l_base, eng == "llm"),
                             (self.model, self.l_model, eng == "llm"), (self.key, self.l_key, eng == "llm"),
                             (self.temp, self.l_temp, eng == "llm")):
            w.setVisible(show)
            lab.setVisible(show)
            g = self._engine_card.grid
            idx = g.indexOf(w)
            if idx >= 0:
                r, _c, _rs, _cs = g.getItemPosition(idx)
                h = g.itemAtPosition(r, 2)
                if h and h.widget():
                    h.widget().setVisible(show)
        self._ep_store()

    def _apply_provider(self, name):
        if name in translator.LLM_PRESETS and not self._loading:
            url, model = translator.LLM_PRESETS[name]
            self.base.setText(url)
            self.model.setText(model)
        self._ep_store()

    # ------------------------------------------------------------ halaman: Typeset & Output, Tentang
    def _build_output(self):
        v = self._page("Typeset & Output", "Batas ukuran huruf otomatis dan tempat file hasil kerja.")
        c = self._card(v, "Teks hasil", "Font, tebal, miring & KAPITAL diatur di halaman Teks (preset).")
        self.maxsize = QSpinBox()
        self.maxsize.setRange(8, 200)
        self.maxsize.setValue(int(self.s["max_font_size"]))
        self._row(c, "Ukuran font maks", self.maxsize, "maxsize")
        self.stroke = QSpinBox()
        self.stroke.setRange(0, 10)
        self.stroke.setValue(int(self.s["default_stroke"]))
        self._row(c, "Stroke default", self.stroke, "stroke")
        c = self._card(v, "File hasil kerja")
        self.fmt = QComboBox()
        self.fmt.addItems(["png", "jpg", "webp"])
        self.fmt.setCurrentText(self.s["output_format"])
        self._row(c, "Format", self.fmt, "fmt")
        row2 = QHBoxLayout()
        self.outdir = QLineEdit(self.s["output_dir"])
        self.outdir.setPlaceholderText("kosong = folder tersembunyi aplikasi (disarankan)")
        b2 = QPushButton("Pilih…")
        b2.setObjectName("gSmall")
        b2.clicked.connect(self._pick_out)
        row2.addWidget(self.outdir, 1)
        row2.addWidget(b2)
        self._row(c, "Folder hasil kerja", row2, "outdir")
        v.addStretch()

    def _build_about(self):
        v = self._page("Tentang", "Informasi aplikasi dan lokasi data pribadimu.")
        c = self._card(v)
        g = c.grid
        g.addWidget(QLabel("Versi"), 0, 0)
        g.addWidget(QLabel(f"<b>Rexxa Translator {version.__version__}</b>"), 0, 1)
        g.addWidget(QLabel("Update"), 1, 0)
        g.addWidget(QLabel("Otomatis — dicek setiap aplikasi dibuka"), 1, 1)
        c = self._card(v, "Data pribadi", "Pengaturan, API key, font & hasil kerja. Aman saat aplikasi di-update.")
        drow = QHBoxLayout()
        dl = QLineEdit(str(paths.data_dir()))
        dl.setReadOnly(True)
        ob = QPushButton("Buka folder")
        ob.setObjectName("gSmall")
        ob.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.data_dir()))))
        drow.addWidget(dl, 1)
        drow.addWidget(ob)
        c.grid.addLayout(drow, 0, 0, 1, 3)
        v.addStretch()

    # ------------------------------------------------------------ simpan
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

    def _pick_out(self):
        d = QFileDialog.getExistingDirectory(self, "Folder hasil kerja")
        if d:
            self.outdir.setText(d)

    def result_settings(self) -> dict:
        s = self.s
        self._ep_store()
        s["engine_preset"] = self._ep_cur
        s.update(self._fields())
        s.update(llm_extra_prompt=self.extra.toPlainText().strip(),
                 detect_mode=self.detect.currentData(), ocr_engine=self.ocr.currentData(),
                 clean_method=self.clean.currentData(), gpu=self.gpu.isChecked(),
                 auto_patch=self.autopatch.isChecked(), auto_lines=self.autolines.isChecked(),
                 tl_style=self.style.currentData(), tl_honorific=self.honor.currentData(),
                 story_memory=self.memory.isChecked(), story_context=self.prevctx.isChecked(),
                 max_font_size=self.maxsize.value(), default_stroke=self.stroke.value(),
                 output_format=self.fmt.currentText(), output_dir=self.outdir.text().strip(),
                 sfx_font_match=self.sfxmatch.isChecked(), font_match_system=self.sysfont.isChecked(),
                 font_match_online=self.gfont.isChecked(), font_match_all=self.fontall.isChecked(),
                 perf_mode=self.perf.currentData() or "auto", _settings_tab=self.nav.currentRow())
        s.update(self.text.values())
        s.update(self.sc.values())
        pipeline.sync_default_style(s)
        return s


class NameDialog(GlassDialog):
    """Kotak kecil untuk mengetik nama (preset, dll.)."""

    def __init__(self, parent, title, current="", taken=()):
        super().__init__(parent, title, "Nama bebas, mis. “Gemini utama” atau “OpenRouter cadangan”.", size=(380, 128),
                         resizable=False)
        self.setStyleSheet(self.styleSheet() + SETTINGS_STYLE)
        self.taken = {t.lower() for t in taken}
        self.edit = QLineEdit(current)
        self.edit.selectAll()
        self.msg = QLabel("")
        self.msg.setObjectName("gSub")
        self.body.addWidget(self.edit)
        self.body.addWidget(self.msg)
        cancel = QPushButton("Batal")
        cancel.setObjectName("gGhost")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("Simpan")
        self.ok.setObjectName("gPrimary")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.accept)
        self.footer.addStretch()
        self.footer.addWidget(cancel)
        self.footer.addWidget(self.ok)
        self.edit.textChanged.connect(self._check)
        self._check()

    def _check(self, *_):
        t = self.value()
        bad = "Nama tidak boleh kosong." if not t else ("Nama ini sudah dipakai." if t.lower() in self.taken else "")
        self.msg.setText(bad)
        self.ok.setEnabled(not bad)

    def value(self) -> str:
        return self.edit.text().strip()[:40]


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
