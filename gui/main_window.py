"""Jendela utama Rexxa Translator.

Tata letak:
  [toolbar ikon satu baris: buka · simpan · kotak · bahasa · TERJEMAHKAN · ◀ 1/9 ▶ · tampilan · export · pengaturan]
  [HALAMAN (thumbnail)] [ ASLI | HASIL  berdampingan, zoom & geser sinkron ] [PROPERTI · BALON · LOG]
  [status bar: status · progres · zoom · jumlah balon]
"""
from __future__ import annotations

import os
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QRectF, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QImageReader, QKeySequence, QPixmap
from .numfield import NumField
from PySide6.QtWidgets import (QAbstractItemView, QAbstractSpinBox, QDoubleSpinBox, QApplication, QCheckBox, QColorDialog, QComboBox,
                               QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
                               QSpinBox, QSplitter, QSplitterHandle, QTableWidget, QTableWidgetItem, QTabWidget,
                               QToolBar, QToolButton, QVBoxLayout, QWidget)

from core import pipeline, typeset
from core.models import IMAGE_EXTS, Project, TextBlock
from core.translator import LANG_NAMES
from core.version import __version__
from .canvas import PageCanvas
from .dialogs import GlossaryDialog, SettingsDialog
from . import shortcuts as SC
from .icons import icon
from .updater import UpdateChecker
from .alert import Alert, MessageBox as QMessageBox  # noqa: E402,F811  (semua alert bergaya Rexxa)

UNDO_LIMIT = 5        # langkah undo per halaman (redo menampung langkah yang di-undo)
APP_NAME = "Rexxa Translator"
SRC_LANGS = ["ja", "ko", "zh", "zh-tw", "en"]
TGT_LANGS = ["id", "en", "ms", "vi", "th", "es", "pt", "fr", "de", "ru", "ja", "ko", "zh"]
SHORT = {"ja": "JP", "ko": "KR", "zh": "CN", "zh-tw": "TW", "en": "EN", "id": "ID", "ms": "MY", "vi": "VI",
         "th": "TH", "es": "ES", "pt": "PT", "fr": "FR", "de": "DE", "ru": "RU"}
STATUS_TXT = {"baru": "Belum diproses", "dideteksi": "Terdeteksi", "di-OCR": "Sudah OCR",
              "diterjemah": "Diterjemahkan", "selesai": "Selesai"}
ACCENT = "#7c6cff"


# ====================================================================== worker
class Worker(QObject):
    log = Signal(str)
    progress = Signal(int, int)
    page_updated = Signal(int)
    finished = Signal(str)   # pesan error, kosong jika sukses

    def __init__(self, job):
        super().__init__()
        self.job = job
        self.stop = False

    def run(self):
        try:
            self.job(self)
            self.finished.emit("")
        except Exception as e:
            self.log.emit(traceback.format_exc())
            self.finished.emit(_friendly(e))


def _friendly(e: Exception) -> str:
    if isinstance(e, ImportError):
        mod = getattr(e, "name", "") or str(e)
        return (f"Modul '{mod}' belum terpasang.\n\nUntuk fitur ini jalankan install_ai.bat "
                f"(atau: pip install {mod.replace('_', '-')}).")
    return str(e)


# ====================================================================== widget kecil
class Section(QWidget):
    """Panel yang bisa dilipat dengan judul huruf kapital (seperti panel properti editor gambar)."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.btn = QToolButton(text=f"  {title.upper()}")
        self.btn.setObjectName("sectionHeader")
        self.btn.setCheckable(True)
        self.btn.setChecked(True)
        self.btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn.setArrowType(Qt.DownArrow)
        self.btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn.toggled.connect(self._toggle)
        self.body = QWidget()
        self.body.setObjectName("sectionBody")
        self.lay = QVBoxLayout(self.body)
        self.lay.setContentsMargins(6, 6, 6, 8)
        self.lay.setSpacing(5)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 6)
        v.setSpacing(0)
        v.addWidget(self.btn)
        v.addWidget(self.body)

    def _toggle(self, on):
        self.btn.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.body.setVisible(on)


def small_label(text):
    l = QLabel(text)
    l.setObjectName("fieldLabel")
    return l


BOX_MODES = [("box", "Tambah kotak saja"),
             ("ocr", "Tambah kotak + OCR (baca teks)"),
             ("ocr_tr", "Tambah kotak + OCR + terjemahkan")]


def tool_btn(name, tip, slot=None, checkable=False, text=None):
    b = QToolButton()
    b.setIcon(icon(name))
    b.setIconSize(QSize(20, 20))
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setAutoRaise(True)
    if text:
        b.setText(text)
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    if slot:
        b.clicked.connect(slot)
    return b


def vline():
    f = QFrame()
    f.setFrameShape(QFrame.VLine)
    f.setObjectName("sep")
    return f


def spacer():
    w = QWidget()
    w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return w


class _ResetHandle(QSplitterHandle):
    def mouseDoubleClickEvent(self, e):
        self.splitter().equalize()


class EqualSplitter(QSplitter):
    """Splitter yang awalnya membagi rata, dan kembali rata saat pembatasnya diklik dua kali."""
    reset_done = Signal()

    def __init__(self, *a):
        super().__init__(*a)
        self._first = True

    def createHandle(self):
        h = _ResetHandle(self.orientation(), self)
        h.setToolTip("Seret untuk mengubah lebar · klik dua kali = kembali 50:50")
        return h

    def equalize(self):
        n = sum(1 for i in range(self.count()) if self.widget(i).isVisible())
        if n:
            self.setSizes([1000] * self.count())   # Qt menyesuaikan secara proporsional -> sama rata
            self.reset_done.emit()

    def showEvent(self, e):
        super().showEvent(e)
        if self._first:
            self._first = False
            QTimer.singleShot(0, self.equalize)


# ====================================================================== window

def _idx(seq, obj) -> int:
    """Indeks berdasarkan identitas objek (bukan kesamaan isi)."""
    for i, x in enumerate(seq):
        if x is obj:
            return i
    return -1


def _has(seq, obj) -> bool:
    return obj is not None and _idx(seq, obj) >= 0

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1500, 920)
        self.setAcceptDrops(True)
        self.settings = pipeline.load_settings()
        self.project = Project(source_lang=self.settings.get("last_source_lang", "ja"),
                               target_lang=self.settings.get("last_target_lang", "id"))
        self.cur = -1
        self.need_clean: set[str] = set()
        self.thread: QThread | None = None
        self.worker: Worker | None = None
        self.sel: TextBlock | None = None
        self.multi: list = []                 # Ctrl+klik: beberapa balon dipilih sekaligus (termasuk self.sel)
        self._loading = False
        self._render_after_job = False

        self.render_timer = QTimer(self, singleShot=True, interval=450)
        self.render_timer.timeout.connect(self._auto_render)
        # hasil render langsung diserahkan ke tampilan (tanpa membaca ulang file dari disk)
        from core import perf
        from . import imgcache
        imgcache.MAX_MB = 60 if perf.low_end(self.settings) else 160
        pipeline.ON_SAVED = imgcache.put_np
        try:
            perf.apply(self.settings)       # batas cache & thread juga berlaku untuk edit / render biasa
        except Exception:
            pass

        self._build_toolbar()
        self._build_center()
        self._build_statusbar()
        self._build_shortcuts()
        self._set_busy(False)
        self._update_title()
        QApplication.instance().installEventFilter(self)     # tahan Spasi = mode tangan
        self._show_current(fit=True)
        self.log(f"{APP_NAME} {__version__} siap. Seret folder/gambar manga ke jendela ini, atau klik ikon folder.")
        try:   # Windows: ikon file .mtproj + buka dengan klik ganda
            from core import fileassoc
            fileassoc.register_async()
        except Exception:
            pass
        self.updater = UpdateChecker(self)
        QTimer.singleShot(1500, self.updater.check)
        if os.environ.get("REXXA_ROLLED_BACK"):
            QTimer.singleShot(800, lambda: QMessageBox.warning(
                self, APP_NAME, "Update terakhir gagal dibuka, jadi Rexxa Translator kembali ke versi "
                                "sebelumnya secara otomatis. Coba update lagi nanti."))

    # ================================================================== toolbar
    def _build_toolbar(self):
        tb = QToolBar("Utama")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(tb)

        m_open = QMenu(self)
        m_open.aboutToShow.connect(lambda: self._fill_open_menu(m_open))
        self._fill_open_menu(m_open)
        b = tool_btn("open", "Buka folder / gambar / proyek")
        b.setMenu(m_open)
        b.setPopupMode(QToolButton.InstantPopup)
        tb.addWidget(b)
        self.b_save = tool_btn("save", "Simpan proyek (Ctrl+S)", self.save_project)
        self.b_undo = tool_btn("undo", "Undo (Ctrl+Z) · maks. 5 langkah", self.undo)
        self.b_redo = tool_btn("redo", "Redo (Ctrl+Y)", self.redo)
        for b_ in (self.b_save, self.b_undo, self.b_redo):
            b_.setEnabled(False)
            tb.addWidget(b_)
        self.b_save.setContextMenuPolicy(Qt.CustomContextMenu)   # klik kanan = Simpan sebagai…
        self.b_save.customContextMenuRequested.connect(
            lambda pos: self._save_menu(self.b_save.mapToGlobal(pos)))
        self._saved_sig = None
        self._dirty = False
        self.state_timer = QTimer(self, interval=600)       # cek perubahan & status undo/redo
        self.state_timer.timeout.connect(self._refresh_state)
        self.state_timer.start()
        tb.addWidget(vline())

        self.b_box = tool_btn("box", "Tambah kotak teks manual (B) · klik panah untuk memilih yang dilakukan "
                                     "setelah kotak dibuat", self.toggle_draw, checkable=True)
        self.b_box.setObjectName("splitBtn")
        from PySide6.QtGui import QActionGroup
        m_box = QMenu(self)
        m_box.addSection("Setelah kotak dibuat")
        self.box_modes = QActionGroup(self)
        self.box_modes.setExclusive(True)
        for mode, label in BOX_MODES:
            a = m_box.addAction(label)
            a.setCheckable(True)
            a.setData(mode)
            a.setChecked(self.settings.get("box_mode", "box") == mode)
            self.box_modes.addAction(a)
        self.box_modes.triggered.connect(self._set_box_mode)
        self.b_box.setMenu(m_box)
        self.b_box.setPopupMode(QToolButton.MenuButtonPopup)
        tb.addWidget(self.b_box)
        # alat sunting gambar
        self.tool_btns = {}
        for tid, ico, tip in (("select", "cursor", "Pilih / geser kotak (V)"),
                              ("pen", "pen", "Pen tool (P): klik titik-titik mengelilingi area, klik titik awal / "
                                             "klik kanan / Enter = selesai. Lalu pilih: hapus dengan AI, isi warna, dll."),
                              ("shape", "shape", "Shape tool (A): seret kotak / oval (Shift = persegi). "
                                                 "Tekan A lagi untuk ganti kotak ↔ oval"),
                              ("heal", "heal", "Healing brush (J): sapukan di atas noda / sisa teks / objek, "
                                               "AI (LaMa) membuat ulang latarnya. [ dan ] = ukuran kuas"),
                              ("patch", "patch", "Patch tool (K): lingkari area yang belum rapi (seret seperti "
                                                 "lasso). AI mencari area latar yang sama persis di halaman lalu "
                                                 "menambalnya dengan pembauran halus — seperti Patch Tool Photoshop"),
                              ("line", "line", "Alat garis (L): gambar garis sendiri, mis. tepi balon yang hilang. "
                                               "Seret = garis bebas, Shift + seret = garis lurus. "
                                               "[ dan ] = tebal garis, klik kotak warna untuk ganti warna")):
            b = tool_btn(ico, tip, checkable=True)
            b.clicked.connect(lambda _=False, t=tid: self.set_tool(t))
            self.tool_btns[tid] = b
            tb.addWidget(b)
        self.tool_btns["select"].setChecked(True)
        self.brush_field = NumField(1, 200, 1, 0, default=14)
        self.brush_field.setToolTip("Ukuran kuas healing brush / tebal garis (px)  ·  [ dan ]")
        self.brush_field.setFixedWidth(44)
        self.brush_field.setEnabled(False)          # aktif saat healing brush / alat garis dipilih
        self._tool_sizes = {"heal": 14, "line": int(self.settings.get("line_width", 3) or 3)}
        self.brush_field.valueChanged.connect(self._on_brush_size)
        tb.addWidget(self.brush_field)
        self.line_color = self.settings.get("line_color", "#000000") or "#000000"
        self.b_line_color = QToolButton()
        self.b_line_color.setObjectName("lineSwatch")
        self.b_line_color.setFixedSize(22, 22)
        self.b_line_color.setToolTip("Warna garis (alat garis & garis tepi)")
        self.b_line_color.clicked.connect(self._pick_line_color)
        self.b_line_color.setEnabled(False)
        self._paint_line_swatch()
        tb.addWidget(self.b_line_color)
        # pratinjau garis -> jadikan garis (muncul hanya saat ada pratinjau)
        self.b_line_ok = QToolButton()
        self.b_line_ok.setObjectName("primary")
        self.b_line_ok.setText(" Jadikan garis")
        self.b_line_ok.setIcon(icon("line", "#ffffff"))
        self.b_line_ok.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.b_line_ok.setToolTip("Ubah pratinjau (garis putus-putus) menjadi garis sungguhan  ·  Enter")
        self.b_line_ok.setPopupMode(QToolButton.MenuButtonPopup)
        self.b_line_ok.clicked.connect(lambda: self._commit_draft(None, "auto"))
        m_line = QMenu(self)
        m_line.aboutToShow.connect(lambda: self._fill_draft_menu(m_line, None))
        self.b_line_ok.setMenu(m_line)
        self.b_line_cancel = tool_btn("close", "Hapus pratinjau garis  ·  Esc", lambda: self._commit_draft(None, "cancel"))
        self._a_line_ok = tb.addWidget(self.b_line_ok)
        self._a_line_cancel = tb.addWidget(self.b_line_cancel)
        self._a_line_ok.setVisible(False)
        self._a_line_cancel.setVisible(False)
        tb.addWidget(vline())

        self.src = QComboBox()
        self.src.setToolTip("Bahasa asli")
        for l in SRC_LANGS:
            self.src.addItem(f"{SHORT.get(l, l)}  {LANG_NAMES.get(l, l)}", l)
        self.src.setCurrentIndex(max(0, self.src.findData(self.project.source_lang)))
        self.src.currentIndexChanged.connect(self._on_lang)
        self.tgt = QComboBox()
        self.tgt.setToolTip("Bahasa tujuan")
        for l in TGT_LANGS:
            self.tgt.addItem(f"{SHORT.get(l, l)}  {LANG_NAMES.get(l, l)}", l)
        self.tgt.setCurrentIndex(max(0, self.tgt.findData(self.project.target_lang)))
        self.tgt.currentIndexChanged.connect(self._on_lang)
        tb.addWidget(self.src)
        arrow = QLabel(" → ")
        arrow.setObjectName("dim")
        tb.addWidget(arrow)
        tb.addWidget(self.tgt)
        tb.addWidget(vline())

        # tombol utama: satu klik = deteksi + OCR + terjemah + render
        m_go = QMenu(self)
        m_go.addAction(icon("zapall"), "Terjemahkan SEMUA halaman  (F6)", self.run_all)
        m_go.addAction(icon("zap"), "Terjemahkan ulang halaman ini dari awal (deteksi ulang)",
                       lambda: self.run_stages(["detect", "ocr", "translate", "render"]))
        m_go.addSeparator()
        m_go.addAction(icon("scan"), "Deteksi balon SEMUA halaman  (Shift+F6)", self.detect_all)
        m_go.addSeparator()
        m_go.addAction(icon("scan"), "Hanya deteksi balon (halaman ini)", lambda: self.run_stages(["detect"]))
        m_go.addAction(icon("scan"), "Hanya OCR", lambda: self.run_stages(["ocr"]))
        m_go.addAction(icon("translate"), "Hanya terjemahkan", lambda: self.run_stages(["translate"]))
        m_go.addAction(icon("wand"), "Koreksi salah baca OCR (semua halaman)…", self.fix_ocr_all)
        m_go.addAction(icon("wand"), "Lupakan font yang diingat proyek ini", self.reset_font_memory)
        m_go.addAction(icon("image"), "Render ulang  (Ctrl+R)", self.render_current)
        m_go.addSeparator()
        m_go.addAction(icon("translate"), "Logo judul seri di halaman ini…", self.make_title)
        self.b_go = QToolButton()
        self.b_go.setObjectName("primary")
        self.b_go.setText("  Terjemahkan")
        self.b_go.setIcon(icon("translate_go", "#ffffff"))
        self.b_go.setIconSize(QSize(18, 18))
        self.b_go.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.b_go.setToolTip("Deteksi → OCR → terjemah → hapus teks → typeset halaman ini (F5)")
        self.b_go.setPopupMode(QToolButton.MenuButtonPopup)
        self.b_go.setMenu(m_go)
        self.b_go.clicked.connect(self.translate_page)
        tb.addWidget(self.b_go)
        self.b_stop = tool_btn("stop", "Hentikan proses", self.stop_job)
        tb.addWidget(self.b_stop)

        tb.addWidget(spacer())
        self.b_prev = tool_btn("prev", "Halaman sebelumnya (PgUp)", lambda: self._step_page(-1))
        tb.addWidget(self.b_prev)
        self.page_lbl = QLabel("0/0")
        self.page_lbl.setObjectName("pageLbl")
        self.page_lbl.setAlignment(Qt.AlignCenter)
        self.page_lbl.setMinimumWidth(56)
        tb.addWidget(self.page_lbl)
        self.b_next = tool_btn("next", "Halaman berikutnya (PgDn)", lambda: self._step_page(1))
        tb.addWidget(self.b_next)
        tb.addWidget(spacer())

        self.b_split = tool_btn("split", "Tampilan berdampingan Asli | Hasil", checkable=True)
        self.b_split.setChecked(True)
        self.b_split.toggled.connect(self._toggle_split)
        tb.addWidget(self.b_split)
        tb.addWidget(vline())

        m_exp = QMenu(self)
        self.a_export_as = m_exp.addAction(icon("export"), "Export As…  (pratinjau, PDF / CBZ / ZIP)", self.export_as)
        m_exp.addAction(icon("project"), "Export skrip terjemahan (.txt)…", self.export_script)
        m_exp.addAction(icon("folderout"), "Buka folder hasil", self.open_output_folder)
        b = tool_btn("export", "Export hasil (Ctrl+E = Export As…)")
        b.setMenu(m_exp)
        b.setPopupMode(QToolButton.InstantPopup)
        tb.addWidget(b)
        self.b_export = b

        m_sk = QMenu(self)
        m_sk.addAction(icon("book"), "Memori cerita (tokoh & panggilan)…", self.edit_story)
        self.m_style = m_sk.addMenu(icon("translate"), "Gaya bahasa")
        self.m_style.aboutToShow.connect(self._fill_style_menu)
        m_sk.addAction(icon("scan"), "Proofread terjemahan…", self.proofread)
        m_sk.addAction(icon("box"), "Kotak judul (buat / tempel logo judul)…", self.title_box)
        m_sk.addSeparator()
        m_sk.addAction(icon("export"), "Halaman kredit & watermark…", self.edit_credits)
        m_sk.addAction(icon("image"), "Export PSD berlapis…", lambda: self.export_as(fmt="psd"))
        b = tool_btn("wand", "Skill: memori cerita, gaya bahasa, proofread, kredit, PSD")
        b.setMenu(m_sk)
        b.setPopupMode(QToolButton.InstantPopup)
        tb.addWidget(b)
        self.b_skill = b

        m_set = QMenu(self)
        m_set.addAction(icon("settings"), "Pengaturan…  (Ctrl+,)", self.edit_settings)
        m_set.addAction(icon("book"), "Glosarium…", self.edit_glossary)
        m_set.addAction(icon("update"), "Cek update", lambda: self.updater.check(manual=True))
        m_set.addSeparator()
        m_set.addAction(f"Rexxa Translator {__version__}").setEnabled(False)
        b = tool_btn("settings", "Pengaturan")
        b.setMenu(m_set)
        b.setPopupMode(QToolButton.InstantPopup)
        tb.addWidget(b)

    def _on_lang(self, *_):
        self.project.source_lang = self.src.currentData()
        self.project.target_lang = self.tgt.currentData()
        # diingat untuk dibuka lagi nanti
        self.settings["last_source_lang"] = self.project.source_lang
        self.settings["last_target_lang"] = self.project.target_lang
        pipeline.save_settings(self.settings)

    # ================================================================== area tengah
    def _build_center(self):
        # ---- kiri: daftar halaman dengan thumbnail
        left = QWidget()
        left.setObjectName("panel")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)
        self.pages_hdr = QLabel("HALAMAN (0)")
        self.pages_hdr.setObjectName("panelHeader")
        self.b_add_page = QToolButton()
        self.b_add_page.setObjectName("hdrBtn")
        self.b_add_page.setIcon(icon("plus"))
        self.b_add_page.setIconSize(QSize(14, 14))
        self.b_add_page.setToolTip("Tambah gambar / halaman baru")
        self.b_add_page.clicked.connect(lambda: self.add_pages())
        hdr = QWidget()
        hdr.setObjectName("pagesHdr")
        hh = QHBoxLayout(hdr)
        hh.setContentsMargins(0, 0, 6, 0)
        hh.setSpacing(0)
        hh.addWidget(self.pages_hdr, 1)
        hh.addWidget(self.b_add_page)
        self.pages = QListWidget()
        self.pages.setIconSize(QSize(34, 48))
        self.pages.setSpacing(2)
        self.pages.currentRowChanged.connect(self.open_page)
        # tahan & seret halaman untuk mengubah urutan; klik kanan = tambah / hapus
        self.pages.setDragDropMode(QAbstractItemView.InternalMove)
        self.pages.setDefaultDropAction(Qt.MoveAction)
        self.pages.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.pages.model().rowsMoved.connect(self._on_pages_moved)
        self.pages.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pages.customContextMenuRequested.connect(self._pages_menu)
        self.pages_empty = QLabel("Seret folder chapter\nke sini, atau klik\nikon folder di atas.")
        self.pages_empty.setObjectName("dim")
        self.pages_empty.setAlignment(Qt.AlignCenter)
        ll.addWidget(hdr)
        ll.addWidget(self.pages, 1)
        ll.addWidget(self.pages_empty, 1)

        # ---- tengah: Asli | Hasil
        self.cv_src = PageCanvas(editable=True)
        self.cv_out = PageCanvas(editable=True, ghost=True)   # sisi Hasil: kotak tak terlihat tapi bisa diklik
        for cv in (self.cv_src, self.cv_out):
            other = self.cv_out if cv is self.cv_src else self.cv_src
            cv.block_selected.connect(self._on_canvas_select)
            cv.block_toggled.connect(self._on_canvas_toggle)
            cv.edit_started.connect(self._on_edit_started)
            cv.block_moving.connect(lambda b, o=other: o.reload_boxes())
            cv.block_geometry_changed.connect(self._on_geom_changed)
            cv.block_double_clicked.connect(self._focus_translation)
        self.cv_src.box_drawn.connect(self._add_box)
        for cv in (self.cv_src, self.cv_out):
            cv.heal_stroke.connect(self._on_heal)
            cv.patch_done.connect(self._on_patch)
            cv.region_done.connect(self._on_region)
            cv.line_stroke.connect(self._on_line)
            cv.draft_changed.connect(lambda on, c=cv: self._on_draft_changed(c, on))
            cv.draft_menu.connect(lambda pos, c=cv: self._draft_menu(c, pos))
        # sinkron zoom & geser
        self.cv_src.zoom_changed.connect(lambda s: self._sync_zoom(self.cv_src, self.cv_out, s))
        self.cv_out.zoom_changed.connect(lambda s: self._sync_zoom(self.cv_out, self.cv_src, s))
        for a, b in ((self.cv_src, self.cv_out), (self.cv_out, self.cv_src)):
            a.horizontalScrollBar().valueChanged.connect(b.horizontalScrollBar().setValue)
            a.verticalScrollBar().valueChanged.connect(b.verticalScrollBar().setValue)

        def column(title, canvas, extra=None):
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(0)
            h = QHBoxLayout()
            h.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(title)
            lbl.setObjectName("viewHeader")
            lbl.setAlignment(Qt.AlignCenter)
            h.addWidget(lbl, 1)
            if extra:
                h.addWidget(extra)
            hw = QWidget()
            hw.setObjectName("viewHeaderBar")
            hw.setLayout(h)
            hw.setFixedHeight(34)   # kedua header sama tinggi -> dua gambar sejajar
            v.addWidget(hw)
            v.addWidget(canvas, 1)
            w.header = lbl
            # lebar ditentukan layout (50:50), bukan isi panel -> kedua panel selalu sama lebar
            w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
            w.setMinimumWidth(120)
            return w

        self.out_mode = QComboBox()
        self.out_mode.addItem("Hasil", "hasil")
        self.out_mode.addItem("Bersih", "bersih")
        self.out_mode.setToolTip("Tampilkan hasil akhir, atau gambar yang teksnya sudah dihapus")
        self.out_mode.currentIndexChanged.connect(lambda: self._show_current())
        self.col_out = column("TERJEMAHAN", self.cv_out, self.out_mode)
        # ASLI | TERJEMAHAN: bisa digeser, default 50:50 (klik dua kali pembatas = kembali 50:50)
        self.views = EqualSplitter(Qt.Horizontal)
        self.views.setObjectName("viewsSplit")
        self.views.setHandleWidth(6)
        self.views.setChildrenCollapsible(False)
        self.col_src = column("ASLI", self.cv_src)
        self.views.addWidget(self.col_src)
        self.views.addWidget(self.col_out)
        self.views.setStretchFactor(0, 1)
        self.views.setStretchFactor(1, 1)
        self.views.splitterMoved.connect(lambda *_: QTimer.singleShot(0, self._fit_both))
        self.views.reset_done.connect(lambda: QTimer.singleShot(0, self._fit_both))

        # ---- kanan: properti / daftar balon / log
        self.tabs = QTabWidget()
        self.tabs.setObjectName("rightTabs")
        self.tabs.addTab(self._build_props(), "PROPERTI")
        self.tabs.addTab(self._build_table(), "BALON")
        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumBlockCount(3000)
        self.tabs.addTab(self.logbox, "LOG")

        split = QSplitter(Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(self.views)
        split.addWidget(self.tabs)
        # sidebar ramping (seperti editor lettering): fokus ke halaman manga
        left.setMinimumWidth(96)
        self.tabs.setMinimumWidth(220)
        split.setSizes([128, 1300, 240])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        split.setChildrenCollapsible(False)
        split.splitterMoved.connect(lambda *_: QTimer.singleShot(0, self._fit_both))
        # layar awal (belum ada gambar) <-> editor; panel samping hanya muncul di editor
        from PySide6.QtWidgets import QStackedWidget
        from .welcome import WelcomeView
        self.welcome = WelcomeView()
        self.welcome.open_folder.connect(self.open_folder)
        self.welcome.open_images.connect(self.open_images)
        self.welcome.open_project.connect(self.open_project)
        self.welcome.files_dropped.connect(self._load_paths)
        self.welcome.open_recent.connect(self._open_recent)
        self.welcome.remove_recent.connect(self._remove_recent)
        self.welcome.clear_recent.connect(self._clear_recent)
        self._show_recent()
        self.center_stack = QStackedWidget()
        self.center_stack.addWidget(self.welcome)
        self.center_stack.addWidget(split)
        self.center_stack.setCurrentIndex(0)
        self.setCentralWidget(self.center_stack)

    def _build_props(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(4)

        self.props_hint = QLabel("Klik sebuah balon di gambar ASLI\nuntuk mengedit teks & gayanya.")
        self.props_hint.setObjectName("dim")
        self.props_hint.setAlignment(Qt.AlignCenter)
        self.props_hint.setWordWrap(True)
        v.addWidget(self.props_hint)

        # --- bar pilihan ganda (Ctrl+klik beberapa balon)
        self.multi_bar = QFrame()
        self.multi_bar.setObjectName("multiBar")
        self.multi_bar.setStyleSheet("#multiBar { background:#22273a; border:1px solid #7c6cff; border-radius:8px; }")
        mb = QVBoxLayout(self.multi_bar)
        mb.setContentsMargins(8, 6, 8, 6)
        mb.setSpacing(4)
        self.multi_lbl = QLabel("")
        self.multi_lbl.setWordWrap(True)
        mb.addWidget(self.multi_lbl)
        mrow = QHBoxLayout()
        mrow.setSpacing(4)
        mrow.addWidget(small_label("Samakan:"))
        b_eq_font = QPushButton("Ukuran teks")
        b_eq_font.setToolTip("Semua balon terpilih memakai ukuran teks balon aktif (yang bergaris pegangan)")
        b_eq_font.clicked.connect(self._equal_font_size)
        b_eq_box = QPushButton("Ukuran kotak")
        b_eq_box.setToolTip("Semua kotak terpilih dibuat selebar & setinggi kotak aktif (posisi tengah tetap)")
        b_eq_box.clicked.connect(self._equal_box_size)
        mrow.addWidget(b_eq_font, 1)
        mrow.addWidget(b_eq_box, 1)
        mb.addLayout(mrow)
        b_clear = QPushButton("Lepas pilihan ganda")
        b_clear.setObjectName("flat")
        b_clear.clicked.connect(lambda: self._select(self.sel))
        mb.addWidget(b_clear)
        hint = QLabel("Ctrl+klik balon di gambar / daftar untuk menambah atau melepas.")
        hint.setObjectName("dim")
        hint.setWordWrap(True)
        mb.addWidget(hint)
        self.multi_bar.setVisible(False)
        v.addWidget(self.multi_bar)

        # --- Terjemahan
        s1 = Section("Terjemahan")
        s1.lay.addWidget(small_label("Teks asli (OCR)"))
        self.e_src = QPlainTextEdit()
        self.e_src.setPlaceholderText("Teks asli hasil OCR…")
        self.e_src.setFixedHeight(52)
        s1.lay.addWidget(self.e_src)
        s1.lay.addWidget(small_label("Terjemahan"))
        self.e_tr = QPlainTextEdit()
        self.e_tr.setPlaceholderText("Tulis / perbaiki terjemahan…  (hasil diperbarui otomatis)")
        self.e_tr.setFixedHeight(72)
        s1.lay.addWidget(self.e_tr)
        row = QHBoxLayout()
        self.b_reocr = QPushButton(icon("scan"), " OCR ulang")
        self.b_reocr.clicked.connect(lambda: self._block_job("ocr"))
        self.b_retr = QPushButton(icon("translate"), " Terjemah ulang")
        self.b_retr.clicked.connect(lambda: self._block_job("tr"))
        row.addWidget(self.b_reocr)
        row.addWidget(self.b_retr)
        s1.lay.addLayout(row)
        self.e_src.textChanged.connect(self._on_src_text)
        self.e_tr.textChanged.connect(self._on_tr_text)

        # --- Tipografi (tata letak seperti editor lettering: baris-baris ringkas)
        # Semua baris boleh MENYEMPIT mengikuti lebar sidebar (tidak ada lebar tetap yang besar),
        # jadi panel tidak terpotong saat sidebar digeser.
        s2 = Section("Tipografi")
        EXP = QSizePolicy.Expanding

        def shrink(wd, minw=18, maxw=None, h=24):
            wd.setMinimumWidth(minw)
            if maxw:
                wd.setMaximumWidth(maxw)
            wd.setFixedHeight(h)
            wd.setSizePolicy(EXP if not maxw or maxw > minw else QSizePolicy.Fixed, QSizePolicy.Fixed)
            return wd

        def row(*items, spacing=4):
            r = QHBoxLayout()
            r.setSpacing(spacing)
            r.setContentsMargins(0, 0, 0, 0)
            for it in items:
                if it is None:
                    r.addStretch()
                elif isinstance(it, tuple):
                    r.addWidget(it[0], it[1])
                else:
                    r.addWidget(it)
            return r

        def field(icon_text, widget, tip):
            box = QWidget()
            box.setObjectName("field")
            h = QHBoxLayout(box)
            h.setContentsMargins(6, 1, 4, 1)
            h.setSpacing(3)
            ic = QLabel(icon_text)
            ic.setObjectName("fieldIcon")
            h.addWidget(ic)
            h.addWidget(widget, 1)
            box.setToolTip(tip)
            box.setMinimumWidth(56)
            box.setSizePolicy(EXP, QSizePolicy.Fixed)
            return box

        def spin(lo, hi, step, dec, special=None, suffix="", default=None):
            return NumField(lo, hi, step, dec, special, suffix, default=default)

        def mini(text, tip, checkable=True, w=30, ico=None):
            b = QToolButton(text="" if ico else text)
            if ico:
                b.setIcon(icon(ico))
                b.setIconSize(QSize(14, 14))
            b.setObjectName("mini")
            b.setCheckable(checkable)
            b.setToolTip(tip)
            return shrink(b, minw=min(w, 20), maxw=w + 8)

        from .fontcombo import FontCombo
        self.p_font = FontCombo()        # nama font tampil dengan font itu sendiri
        self.p_font.addItem("Font default", "")
        for f in typeset.list_fonts():
            self.p_font.addItem(typeset.font_name(f), f)
        self.p_font.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.p_font.setMinimumContentsLength(6)
        self.p_font.setSizePolicy(EXP, QSizePolicy.Fixed)
        self.p_match = mini("", "Cocokkan font: cari font (aplikasi / perangkat / Google Fonts) yang paling "
                                "mirip dengan teks asli", checkable=False, w=26, ico="wand")
        self.p_match.clicked.connect(self._match_font)
        s2.lay.addLayout(row((self.p_font, 1), self.p_match))

        # ukuran | preset 1–5
        self.p_size = spin(0, 300, 1, 0, "Auto")
        self.p_presets = []
        prow = QHBoxLayout()
        prow.setSpacing(2)
        for n in range(1, 6):
            b = mini(str(n), "", w=24)
            b.setObjectName("presetBtn")
            b.clicked.connect(lambda _=False, n=n: self.apply_preset(n))
            self.p_presets.append(b)
            prow.addWidget(b, 1)
        r1 = QHBoxLayout()
        r1.setSpacing(6)
        r1.addWidget(field("A", self.p_size, "Ukuran font (Auto = menyesuaikan balon)"), 5)
        r1.addLayout(prow, 6)
        s2.lay.addLayout(r1)
        self._update_preset_tips()

        # B I AA Aa aa | rata
        self.p_bold = mini("B", "Tebal", w=26)
        fb = self.p_bold.font(); fb.setBold(True); self.p_bold.setFont(fb)
        self.p_ital = mini("I", "Miring", w=26)
        fi = self.p_ital.font(); fi.setItalic(True); self.p_ital.setFont(fi)
        self.p_case = {}
        for key, txt, tip in (("upper", "AA", "HURUF KAPITAL"), ("none", "Aa", "Huruf biasa (sesuai terjemahan)"),
                              ("lower", "aa", "huruf kecil")):
            b = mini(txt, tip + " · klik lagi = ikut default", w=26)
            b.clicked.connect(lambda _=False, k=key: self._set_case(k))
            self.p_case[key] = b
        self.p_al = {}
        for k, ic in (("left", "al_left"), ("center", "al_center"), ("right", "al_right")):
            b = mini("", {"left": "Rata kiri", "center": "Rata tengah", "right": "Rata kanan"}[k], w=24, ico=ic)
            b.clicked.connect(lambda _=False, k=k: self._set_align(k))
            self.p_al[k] = b
        r2 = QHBoxLayout()
        r2.setSpacing(2)
        for b in (self.p_bold, self.p_ital, *self.p_case.values()):
            r2.addWidget(b, 1)
        r2.addSpacing(6)
        for b in self.p_al.values():
            r2.addWidget(b, 1)
        s2.lay.addLayout(r2)

        # jarak baris | jarak huruf
        self.p_lsp = spin(0.5, 3.0, 0.05, 2, default=float(self.settings.get("line_spacing", 1.2) or 1.2))
        self.p_ls = spin(-10.0, 40.0, 0.5, 1, default=0.0)
        r3 = QHBoxLayout()
        r3.setSpacing(6)
        r3.addWidget(field("≡", self.p_lsp, "Jarak antar baris (1.20 = default dari Pengaturan → Teks)"), 1)
        r3.addWidget(field("AV", self.p_ls, "Jarak antar huruf (piksel)"), 1)
        s2.lay.addLayout(r3)

        # jumlah baris (kelola baris teks terjemahan)
        self.p_lines = spin(0, 20, 1, 0, "Auto", " baris", default=0)
        self.p_lines_m = mini("−", "Kurangi 1 baris (teks lebih lebar)", checkable=False, w=24)
        self.p_lines_p = mini("+", "Tambah 1 baris (teks lebih ramping)", checkable=False, w=24)
        self.p_lines_m.clicked.connect(lambda: self._step_lines(-1))
        self.p_lines_p.clicked.connect(lambda: self._step_lines(1))
        r3b = QHBoxLayout()
        r3b.setSpacing(4)
        r3b.addWidget(field("☰", self.p_lines, "Jumlah baris teks. Auto = menyesuaikan balon. Angka = teks "
                                               "dibagi tepat sebanyak itu dengan panjang baris serata mungkin. "
                                               "Tip: tekan Enter di kolom terjemahan untuk memilih sendiri di "
                                               "mana baris dipotong, lalu atur jumlah baris yang sama."), 3)
        r3b.addWidget(self.p_lines_m, 1)
        r3b.addWidget(self.p_lines_p, 1)
        s2.lay.addLayout(r3b)

        # rotasi | geser posisi (ikon panah)
        self.p_rot = spin(-180, 180, 1, 0, None, "°", default=0)
        r4 = QHBoxLayout()
        r4.setSpacing(6)
        r4.addWidget(field("↻", self.p_rot, "Putar teks (derajat)"), 1)
        pad = QHBoxLayout()
        pad.setSpacing(2)
        for ico, dx, dy, tip in (("mv_left", -1, 0, "Geser kiri"), ("mv_up", 0, -1, "Geser atas"),
                                 ("mv_down", 0, 1, "Geser bawah"), ("mv_right", 1, 0, "Geser kanan"),
                                 ("mv_reset", 0, 0, "Kembalikan ke posisi semula")):
            b = mini("", tip + (" (Shift = 10 px)" if dx or dy else ""), checkable=False, w=24, ico=ico)
            b.setAutoRepeat(bool(dx or dy))
            b.setAutoRepeatDelay(350)
            b.setAutoRepeatInterval(60)
            b.clicked.connect(lambda _=False, dx=dx, dy=dy: self._nudge(dx, dy))
            pad.addWidget(b, 1)
        posbox = QWidget()
        posbox.setToolTip("Geser posisi teks")
        posbox.setLayout(pad)
        pad.setContentsMargins(0, 0, 0, 0)
        posbox.setSizePolicy(EXP, QSizePolicy.Fixed)
        r4.addWidget(posbox, 1)
        s2.lay.addLayout(r4)

        # warna teks (+ gradasi) | ambil dari teks asli
        def swatch(tip, slot):
            b = QPushButton()
            b.setObjectName("swatch")
            b.setToolTip(tip)
            b.clicked.connect(slot)
            return shrink(b, minw=20, maxw=44, h=22)
        self.p_color = swatch("Warna teks", lambda: self._pick_color("color"))
        self.p_color2 = swatch("Gradasi: warna bagian bawah teks (klik untuk memilih)", lambda: self._pick_color("color2"))
        self.p_grad_off = mini("", "Hapus gradasi (warna polos)", checkable=False, w=22, ico="close")
        self.p_grad_off.clicked.connect(self._clear_gradient)
        self.p_gradset = mini("", "Atur gradasi: bentuk (linear, cermin, oval, pisah 2), arah, posisi, kehalusan",
                              checkable=False, w=22, ico="gradient")
        self.p_gradset.clicked.connect(self._gradient_dialog)
        self.p_pick = mini("", "Ambil warna dari teks asli (isi, garis tepi, gradasi)", checkable=False, w=22,
                           ico="eyedrop")
        self.p_pick.clicked.connect(self._pick_from_source)
        lt = small_label("Teks")
        lt.setMinimumWidth(38)
        r5 = QHBoxLayout()
        r5.setSpacing(4)
        r5.addWidget(lt)
        r5.addWidget(self.p_color, 1)
        r5.addWidget(self.p_color2, 1)
        r5.addWidget(self.p_grad_off)
        r5.addWidget(self.p_gradset)
        r5.addStretch(0)
        r5.addWidget(self.p_pick)
        s2.lay.addLayout(r5)

        # garis tepi (stroke)
        self.p_stroke_color = swatch("Warna stroke (garis tepi huruf)", lambda: self._pick_color("stroke_color"))
        self.p_stroke = spin(0, 15, 1, 0, "-")
        self.p_stroke.setToolTip("Tebal stroke (- = tanpa stroke)")
        ls_ = small_label("Stroke")
        ls_.setMinimumWidth(38)
        r6 = QHBoxLayout()
        r6.setSpacing(4)
        r6.addWidget(ls_)
        r6.addWidget(self.p_stroke_color, 1)
        r6.addWidget(field("px", self.p_stroke, "Tebal stroke"), 2)
        s2.lay.addLayout(r6)
        self.p_font.currentIndexChanged.connect(self._on_prop_change)
        for sp in (self.p_size, self.p_stroke, self.p_lsp, self.p_ls, self.p_rot, self.p_lines):   # jangan pakai nama `w`!
            sp.valueChanged.connect(self._on_prop_change)
        self.p_bold.toggled.connect(self._on_prop_change)
        self.p_ital.toggled.connect(self._on_italic)

        # --- Balon
        s3 = Section("Balon")
        self.p_kind = QComboBox()
        self.p_kind.addItem("Balon kata", "bubble")
        self.p_kind.addItem("Teks bebas / SFX / narasi", "free")
        self.p_kind.addItem("Logo judul seri", "title")
        self.p_kind.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.p_kind.setMinimumContentsLength(6)
        self.p_clean = QCheckBox("Hapus teks asli di area ini")
        self.b_del = QPushButton(icon("trash", "#ff8a95"), " Hapus balon ini")
        self.b_del.setObjectName("danger")
        self.b_del.clicked.connect(self.delete_selected)
        s3.lay.addWidget(self.p_kind)
        self.b_title = QPushButton(icon("wand"), " Pembuat judul / tempel judul…")
        self.b_title.setToolTip("Buat logo judul dari teks (gaya mirip aslinya) atau tempel judul buatan sendiri "
                                "(Ctrl+V saat kotak judul dipilih)")
        self.b_title.clicked.connect(lambda: self.edit_title())
        self.b_title.setVisible(False)
        s3.lay.addWidget(self.b_title)
        s3.lay.addWidget(self.p_clean)
        s3.lay.addWidget(self.b_del)
        self.p_kind.currentIndexChanged.connect(self._on_prop_change)
        self.p_clean.toggled.connect(self._on_prop_change)

        self.sections = (s1, s2, s3)
        for s in self.sections:
            v.addWidget(s)
        v.addStretch()
        w.setObjectName("propsPanel")
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setWidget(w)
        return sc

    def _build_table(self):
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["#", "Asli", "Terjemahan"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)   # Ctrl / Shift+klik = pilih banyak
        self.table.setWordWrap(True)
        self.table.verticalHeader().hide()
        self.table.itemChanged.connect(self._on_table_edit)
        self.table.itemSelectionChanged.connect(self._on_table_select)
        return self.table

    def _build_statusbar(self):
        sb = self.statusBar()
        self.status_lbl = QLabel("Siap")
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.setMaximumHeight(10)
        self.progress.setTextVisible(False)
        sb.addWidget(self.status_lbl)
        sb.addWidget(self.progress)
        zb = QWidget()
        zl = QHBoxLayout(zb)
        zl.setContentsMargins(0, 0, 0, 0)
        zl.setSpacing(2)
        zl.addWidget(tool_btn("minus", "Perkecil", lambda: self._zoom_step(1 / 1.25)))
        self.zoom_lbl = QLabel("100%")
        self.zoom_lbl.setMinimumWidth(44)
        self.zoom_lbl.setAlignment(Qt.AlignCenter)
        zl.addWidget(self.zoom_lbl)
        zl.addWidget(tool_btn("plus", "Perbesar", lambda: self._zoom_step(1.25)))
        zl.addWidget(tool_btn("fit", "Pas layar (F)", self._fit_both))
        sb.addPermanentWidget(zb)
        self.count_lbl = QLabel("0 balon")
        self.count_lbl.setObjectName("dim")
        sb.addPermanentWidget(self.count_lbl)

    def _build_shortcuts(self):
        """Buat aksi untuk setiap pintasan di gui/shortcuts.py; tombolnya bisa diubah di Pengaturan."""
        handlers = {
            "open": self.open_folder,
            "save": self.save_project,
            "save_as": self.save_project_as,
            "settings": self.edit_settings,
            "export": self.export_as,
            "paste_title": self.paste_title,
            "translate_page": self.translate_page,
            "translate_all": self.run_all,
            "detect_all": self.detect_all,
            "render": self.render_current,
            "undo": self.undo,
            "redo": self.redo,
            "redo_alt": self.redo,
            "box": lambda: (self.b_box.toggle(), self.toggle_draw()),
            "tool_select": lambda: self.set_tool("select"),
            "tool_pen": lambda: self.set_tool("pen"),
            "tool_shape": self._shape_key,
            "tool_heal": lambda: self.set_tool("heal"),
            "tool_line": lambda: self.set_tool("line"),
            "tool_patch": lambda: self.set_tool("patch"),
            "brush_up": lambda: self._brush_step(1.25),
            "brush_down": lambda: self._brush_step(0.8),
            "delete": lambda: self.delete_pages() if self.pages.hasFocus() else self.delete_selected(),
            "next_page": lambda: self._step_page(1),
            "prev_page": lambda: self._step_page(-1),
            "fit": self._fit_both,
        }
        for n in range(1, 6):
            handlers[f"preset{n}"] = lambda n=n: self.apply_preset(n)
        self._shortcut_actions = {}
        for sid, _group, label, _default, local in SC.SHORTCUTS:
            a = QAction(label, self)
            a.triggered.connect(handlers[sid])
            if local:  # hanya saat fokus di gambar/daftar halaman (tidak bentrok saat mengetik)
                a.setShortcutContext(Qt.WidgetWithChildrenShortcut)
                for w in (self.cv_src, self.cv_out, self.pages):
                    w.addAction(a)
            else:
                self.addAction(a)
            self._shortcut_actions[sid] = a
        self.apply_shortcuts()

    def apply_shortcuts(self):
        for sid, seq in SC.current(self.settings).items():
            a = self._shortcut_actions.get(sid)
            if a:
                a.setShortcut(QKeySequence(seq) if seq else QKeySequence())

    # ================================================================== util
    def log(self, msg: str):
        self.logbox.appendPlainText(msg)
        last = msg.strip().splitlines()[-1] if msg.strip() else ""
        if last and not last.startswith(("Traceback", "  File")):
            self.status_lbl.setText(last[:120])

    def page(self):
        return self.project.pages[self.cur] if 0 <= self.cur < len(self.project.pages) else None

    def _update_title(self):
        p = self.page()
        name = Path(self.project.file).name if self.project.file else (p.name if p else "")
        mark = " •" if getattr(self, "_dirty", False) else ""
        self.setWindowTitle(f"{APP_NAME} {__version__}" + (f" — {name}{mark}" if name else ""))

    def _set_busy(self, busy: bool):
        self.b_go.setEnabled(not busy)
        self.b_stop.setEnabled(busy)
        self.b_reocr.setEnabled(not busy)
        self.b_retr.setEnabled(not busy)
        if not busy:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)

    @staticmethod
    def _thumb(path) -> QIcon:
        from . import imgcache
        t = imgcache.thumb(path)
        if t is not None:                      # baru dirender: pakai gambar di memori
            return QIcon(QPixmap.fromImage(t))
        r = QImageReader(path)
        r.setAutoTransform(True)
        s = r.size()
        if s.isValid() and s.height() > 0:
            r.setScaledSize(QSize(max(1, int(s.width() * 128 / s.height())), 128))
        return QIcon(QPixmap.fromImage(r.read()))

    def _refresh_page_list(self):
        self.pages.blockSignals(True)
        self.pages.clear()
        for i, p in enumerate(self.project.pages):
            it = QListWidgetItem(self._thumb(p.output_path if p.output_path and Path(p.output_path).exists()
                                             else p.path), "")
            self.pages.addItem(it)
            self._update_page_item(i)
        self.pages.blockSignals(False)
        n = len(self.project.pages)
        self.pages_hdr.setText(f"HALAMAN ({n})")
        self.pages.setVisible(n > 0)
        self.pages_empty.setVisible(n == 0)
        if hasattr(self, "center_stack"):
            was = self.center_stack.currentIndex()
            self.center_stack.setCurrentIndex(1 if n else 0)
            if n and was == 0:
                QTimer.singleShot(0, self._fit_both)
        if 0 <= self.cur < n:
            self.pages.setCurrentRow(self.cur)

    # ------------------------------------------------------------------ kelola halaman
    def add_pages(self, after: int | None = None):
        """Tambah gambar baru ke proyek (di akhir, atau setelah halaman `after`)."""
        if self.thread:
            return
        start = str(Path(self.project.pages[0].path).parent) if self.project.pages else ""
        fs, _ = QFileDialog.getOpenFileNames(self, "Tambah gambar", start,
                                             "Gambar (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not fs:
            return
        from core.models import Page, natural_key
        have = {p.path for p in self.project.pages}
        new = [Page(path=str(f)) for f in sorted(fs, key=natural_key) if str(f) not in have]
        if not new:
            QMessageBox.information(self, APP_NAME, "Gambar itu sudah ada di proyek.")
            return
        pos = len(self.project.pages) if after is None else max(0, min(len(self.project.pages), after + 1))
        keep = self.page()
        self.project.pages[pos:pos] = new
        self.cur = self.project.pages.index(keep) if keep is not None else -1
        self._refresh_page_list()
        target = pos if (after is not None or keep is None) else self.cur
        if target != self.pages.currentRow():
            self.pages.setCurrentRow(target)
        elif target != self.cur or self.page() is None:
            self.open_page(target)
        self.log(f"{len(new)} gambar ditambahkan (sekarang {len(self.project.pages)} halaman).")

    def _on_pages_moved(self, _parent, start, end, _dest, row):
        """Urutan di daftar diubah dengan seret & lepas -> ikuti di proyek."""
        pages = self.project.pages
        cur_page = self.page()
        n = end - start + 1
        moving = pages[start:end + 1]
        rest = pages[:start] + pages[end + 1:]
        to = row - n if row > start else row
        to = max(0, min(len(rest), to))
        self.project.pages = rest[:to] + moving + rest[to:]
        QTimer.singleShot(0, lambda: self._after_reorder(cur_page))

    def _after_reorder(self, cur_page):
        self.cur = self.project.pages.index(cur_page) if cur_page in self.project.pages else 0
        self._refresh_page_list()
        self.pages.blockSignals(True)
        self.pages.setCurrentRow(self.cur)
        self.pages.blockSignals(False)
        self._update_title()
        self.log("Urutan halaman diubah.")

    def _pages_menu(self, pos):
        it = self.pages.itemAt(pos)
        rows = sorted({self.pages.row(i) for i in self.pages.selectedItems()})
        if it is not None and self.pages.row(it) not in rows:
            rows = [self.pages.row(it)]
        m = QMenu(self)
        if rows:
            r0 = rows[0]
            m.addAction(icon("image"), "Buka halaman ini", lambda: self.pages.setCurrentRow(r0)).setEnabled(
                len(rows) == 1)
        m.addAction(icon("plus"), "Tambah gambar di akhir…", lambda: self.add_pages())
        if rows:
            m.addAction(icon("plus"), "Sisipkan gambar setelah halaman ini…",
                        lambda: self.add_pages(after=rows[-1]))
            m.addSeparator()
            if len(rows) == 1:
                m.addAction(icon("prev"), "Pindah ke atas", lambda: self._move_page(rows[0], -1)).setEnabled(rows[0] > 0)
                m.addAction(icon("next"), "Pindah ke bawah", lambda: self._move_page(rows[0], 1)).setEnabled(
                    rows[0] < len(self.project.pages) - 1)
                m.addSeparator()
            label = "Hapus halaman ini" if len(rows) == 1 else f"Hapus {len(rows)} halaman terpilih"
            m.addAction(icon("close"), label + "  (Delete)", lambda: self.delete_pages(rows))
        m.exec(self.pages.viewport().mapToGlobal(pos))

    def _move_page(self, i, d):
        j = i + d
        pages = self.project.pages
        if not (0 <= i < len(pages) and 0 <= j < len(pages)):
            return
        cur_page = self.page()
        pages[i], pages[j] = pages[j], pages[i]
        self._after_reorder(cur_page)

    def delete_pages(self, rows=None):
        """Hapus halaman dari proyek (file gambarnya tidak dihapus dari komputer)."""
        if self.thread:
            return
        if rows is None:
            rows = sorted({self.pages.row(i) for i in self.pages.selectedItems()}) or \
                ([self.cur] if self.cur >= 0 else [])
        rows = [r for r in rows if 0 <= r < len(self.project.pages)]
        if not rows:
            return
        names = ", ".join(self.project.pages[r].name for r in rows[:3]) + ("…" if len(rows) > 3 else "")
        from .alert import ask
        if not ask(self, APP_NAME, f"Hapus {len(rows)} halaman dari proyek?\n{names}\n\nFile gambarnya tidak "
                   "dihapus dari komputer. Balon & terjemahan di halaman itu ikut hilang dari proyek.",
                   yes="Hapus", no="Batal", kind="warn", danger=True):
            return
        cur_page = self.page()
        gone = {id(self.project.pages[r]) for r in rows}
        self.project.pages = [p for p in self.project.pages if id(p) not in gone]
        if cur_page is not None and id(cur_page) not in gone:
            self.cur = self.project.pages.index(cur_page)
        else:
            self.cur = min(rows[0], len(self.project.pages) - 1)
        self.sel = None
        self._refresh_page_list()
        if self.project.pages:
            c = max(0, self.cur)
            self.pages.blockSignals(True)
            self.pages.setCurrentRow(c)
            self.pages.blockSignals(False)
            self.open_page(c)
        else:
            self.cur = -1
            for cv in (self.cv_src, self.cv_out):
                cv.set_page(None, [])
        self._update_title()
        self.log(f"{len(rows)} halaman dihapus dari proyek.")

    def _update_page_item(self, i):
        if 0 <= i < self.pages.count():
            p = self.project.pages[i]
            it = self.pages.item(i)
            it.setText(f"Hal {i + 1}\n{STATUS_TXT.get(p.status, p.status)}")
            f = it.font(); f.setPointSizeF(8); it.setFont(f)
            it.setToolTip(p.path)
            it.setForeground(QColor("#7ee2b8") if p.status == "selesai" else QColor("#c8cede"))

    def _step_page(self, d):
        n = len(self.project.pages)
        if n:
            self.pages.setCurrentRow(max(0, min(n - 1, self.cur + d)))

    # ================================================================== zoom & tampilan
    def _sync_zoom(self, src, dst, s):
        self._fit_pending = False
        if abs(dst.zoom() - s) > 1e-4:
            dst.set_zoom(s)
            dst.horizontalScrollBar().setValue(src.horizontalScrollBar().value())
            dst.verticalScrollBar().setValue(src.verticalScrollBar().value())
        self.zoom_lbl.setText(f"{round(s * 100)}%")

    def _fit_both(self):
        """Asli & Hasil memakai skala yang SAMA (yang muat di kedua panel), lalu dipusatkan."""
        self._fit_pending = True
        cvs = [self.cv_src] + ([self.cv_out] if self.col_out.isVisible() and self.cv_out.pix_item else [])
        if not self.cv_src.pix_item:
            return
        s = min(cv.fit_scale() for cv in cvs)
        for cv in (self.cv_src, self.cv_out):
            cv.set_zoom(s)
            if cv.pix_item:
                cv._center_or_top()
        self.zoom_lbl.setText(f"{round(s * 100)}%")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if getattr(self, "_fit_pending", True):   # tetap pas layar sampai pengguna zoom sendiri
            QTimer.singleShot(0, self._fit_both)

    def _zoom_step(self, f):
        self.cv_src.set_zoom(self.cv_src.zoom() * f, emit=True)

    def _toggle_split(self, on):
        self.col_out.setVisible(on)
        if on:
            QTimer.singleShot(0, self.views.equalize)
        QTimer.singleShot(0, self._fit_both)

    # ================================================================== buka / simpan
    def _load_paths(self, paths):
        imgs, folders = [], []
        for p in paths:
            pp = Path(p)
            if pp.is_dir():
                folders.append(pp)
            elif pp.suffix.lower() in IMAGE_EXTS:
                imgs.append(str(pp))
            elif pp.suffix.lower() == ".mtproj":
                return self._load_project(str(pp))
        for f in folders:
            self.project.add_folder(f)
        self.project.add_images(imgs)
        self._refresh_page_list()
        if self.cur < 0 and self.project.pages:
            self.pages.setCurrentRow(0)
        self.log(f"{len(self.project.pages)} halaman dimuat.")
        self._auto_story()
        self._warm_up_ai()

    def open_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih folder chapter")
        if d:
            self._load_paths([d])

    def open_images(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Pilih gambar", "", "Gambar (*.png *.jpg *.jpeg *.webp *.bmp)")
        if fs:
            self._load_paths(fs)

    def open_project(self):
        f, _ = QFileDialog.getOpenFileName(self, "Buka proyek", "", "Proyek Rexxa Translator (*.mtproj)")
        if f:
            self._load_project(f)

    def _load_project(self, f):
        try:
            self.project = Project.load(f)
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Gagal membuka proyek:\n{e}")
            return
        pipeline.mark_clean_valid(self.project)    # hasil bersih tersimpan langsung dipakai
        n_fix = pipeline.sanitize_fonts(self.project)
        if n_fix:
            self.log(f"{n_fix} balon memakai font hiasan hasil pilih otomatis → diganti font biasa "
                     "(render ulang halaman untuk memperbarui hasil).")
            QTimer.singleShot(400, lambda: self.render_current(quiet=True))
        self._history = {}
        self._saved_sig = None                     # dihitung ulang: proyek yang baru dibuka = tersimpan
        self._warm_up_ai()
        self.src.setCurrentIndex(max(0, self.src.findData(self.project.source_lang)))
        self.tgt.setCurrentIndex(max(0, self.tgt.findData(self.project.target_lang)))
        self.cur = -1
        self._refresh_page_list()
        if self.project.pages:
            self.pages.setCurrentRow(0)
        self._update_title()
        self.log(f"Proyek dibuka: {f}")
        self._auto_story()
        self._add_recent(f)

    def _warm_up_ai(self):
        """Muat model AI hapus-teks (LaMa) di latar belakang supaya render pertama tidak lama."""
        if getattr(self, "_warmed", False):
            return
        self._warmed = True
        import threading
        from core import inpaint
        threading.Thread(target=inpaint.warm_up, daemon=True).start()

    def _save_menu(self, gpos):
        m = QMenu(self)
        m.addAction(icon("save"), "Simpan  (Ctrl+S)", self.save_project).setEnabled(self._dirty)
        m.addAction(icon("save"), "Simpan sebagai…  (Ctrl+Shift+S)", self.save_project_as).setEnabled(
            bool(self.project.pages))
        m.exec(gpos)

    def save_project_as(self) -> bool:
        """Simpan ke file proyek BARU (file lama tetap seperti terakhir disimpan)."""
        return self.save_project(ask_path=True)

    def save_project(self, ask_path: bool = False) -> bool:
        """True bila tersimpan (False = dibatalkan)."""
        if not self.project.pages:
            return False
        if ask_path or not self.project.file:
            if self.project.file:
                cur = Path(self.project.file)
                default = str(cur.with_name(cur.stem + " (salinan).mtproj")) if ask_path else str(cur)
            else:
                default = str(Path(self.project.pages[0].path).parent / "untitled.mtproj")
            f, _ = QFileDialog.getSaveFileName(self, "Simpan proyek sebagai" if ask_path else "Simpan proyek",
                                               default, "Proyek Rexxa Translator (*.mtproj)")
            if not f:
                return False
            if not f.lower().endswith(".mtproj"):
                f += ".mtproj"
            self.project.file = f
        self._spin_save_start()
        try:
            self.project.save()
        except Exception as e:
            self._spin_save_stop()
            QMessageBox.critical(self, APP_NAME, f"Gagal menyimpan proyek:\n{e}")
            return False
        self._save_done = True          # animasi berhenti setelah minimal 2 putaran
        self._mark_saved()
        self.log(f"Tersimpan: {self.project.file}")
        self._add_recent(self.project.file)
        return True

    # ------------------------------------------------------------------ animasi tombol simpan
    SAVE_TURN_MS = 420      # 1 putaran
    SAVE_MIN_TURNS = 2

    def _spin_save_start(self):
        """Ikon simpan berputar selama menyimpan (minimal 2 putaran), lalu kembali normal."""
        from PySide6.QtCore import QEasingCurve, QVariantAnimation
        from PySide6.QtGui import QPainter, QTransform
        self._spin_save_stop()
        size = 40
        base = icon("save", "#9182ff").pixmap(QSize(size, size))
        self._save_done = False
        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(360.0)
        anim.setDuration(self.SAVE_TURN_MS)
        anim.setEasingCurve(QEasingCurve.Linear)
        anim.setLoopCount(-1)

        def frame(v):
            pm = QPixmap(base.size())
            pm.setDevicePixelRatio(base.devicePixelRatio())
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            w, h = base.width() / base.devicePixelRatio(), base.height() / base.devicePixelRatio()
            p.setTransform(QTransform().translate(w / 2, h / 2).rotate(float(v)).translate(-w / 2, -h / 2))
            p.drawPixmap(0, 0, base)
            p.end()
            self.b_save.setIcon(QIcon(pm))

        def loop(n):          # n = jumlah putaran yang sudah selesai
            if self._save_done and n >= self.SAVE_MIN_TURNS:
                self._spin_save_stop()

        anim.valueChanged.connect(frame)
        anim.currentLoopChanged.connect(loop)
        self._save_anim = anim
        self.b_save.setEnabled(True)
        anim.start()

    def _spin_save_stop(self):
        anim = getattr(self, "_save_anim", None)
        if anim is None:
            return
        self._save_anim = None
        anim.stop()
        anim.deleteLater()
        self.b_save.setIcon(icon("save_dirty" if self._dirty else "save"))
        self._refresh_state()

    # ------------------------------------------------------------------ status simpan & undo/redo
    def _project_sig(self) -> str:
        """Sidik isi proyek (tanpa path file hasil render) untuk mendeteksi perubahan."""
        import hashlib
        import json
        pr = self.project
        data = {"src": pr.source_lang, "tgt": pr.target_lang, "glossary": pr.glossary,
                "title": getattr(pr, "series_title", ""), "story": getattr(pr, "story", {}),
                "meta": getattr(pr, "export_meta", {}),
                "pages": [{"path": p.path, "edits": p.edits, "blocks": [b.to_dict() for b in p.blocks]}
                          for p in pr.pages]}
        return hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    def _fill_open_menu(self, m):
        """Menu ikon folder (diisi ulang setiap dibuka supaya riwayat proyek selalu terbaru)."""
        m.clear()
        m.addAction(icon("open"), "Buka folder chapter…  (Ctrl+O)", self.open_folder)
        m.addAction(icon("image"), "Buka gambar…", self.open_images)
        m.addAction(icon("project"), "Buka proyek (.mtproj)…", self.open_project)
        rec = m.addMenu(icon("project"), "Proyek terakhir")
        items = [p for p in (self.settings.get("recent_projects") or []) if Path(p).exists()][:10]
        cur = os.path.normcase(os.path.abspath(self.project.file)) if self.project.file else ""
        for n, f in enumerate(items, 1):
            from .welcome import ago
            ts = (self.settings.get("recent_opened") or {}).get(f)
            when = f"   ·   {ago(ts)}" if ts else ""
            a = rec.addAction(f"{n}.  {Path(f).stem}{when}", lambda f=f: self._open_recent(f))
            a.setToolTip(f)
            a.setStatusTip(f)
            if os.path.normcase(os.path.abspath(f)) == cur:
                a.setText(a.text() + "   (sedang dibuka)")
                a.setEnabled(False)
        if not items:
            rec.addAction("Belum ada proyek").setEnabled(False)
        else:
            rec.setToolTipsVisible(True)
            rec.addSeparator()
            rec.addAction(icon("close"), "Hapus riwayat", self._clear_recent)
        m.addSeparator()
        m.addAction(icon("save"), "Simpan proyek  (Ctrl+S)", self.save_project).setEnabled(bool(self.project.pages))
        m.addAction(icon("save"), "Simpan sebagai…  (Ctrl+Shift+S)", self.save_project_as).setEnabled(
            bool(self.project.pages))
        m.addSeparator()
        m.addAction(icon("home"), "Kembali ke layar awal", self.go_home).setEnabled(bool(self.project.pages))

    def go_home(self):
        """Tutup proyek yang sedang dibuka (tanya simpan dulu) dan kembali ke layar awal."""
        if self.thread:
            QMessageBox.information(self, APP_NAME, "Tunggu proses yang sedang berjalan selesai, "
                                    "atau tekan Stop dulu.")
            return
        if not self.confirm_unsaved():
            return
        self.project = Project(source_lang=self.project.source_lang, target_lang=self.project.target_lang)
        self.cur = -1
        self.sel = None
        self._history = {}
        self._saved_sig = None
        self._dirty = False
        self.need_clean.clear()
        for cv in (self.cv_src, self.cv_out):
            cv.clear_draft()
            cv.set_page(None, [])
        self._refresh_page_list()
        self.b_save.setIcon(icon("save"))
        try:
            self._load_props(None)
        except Exception:
            pass
        self._show_recent()
        self._refresh_state()
        self._update_title()
        self.log("Kembali ke layar awal.")

    def _clear_recent(self):
        self.settings["recent_projects"] = []
        self.settings["recent_opened"] = {}
        pipeline.save_settings(self.settings)
        self._show_recent()

    # ------------------------------------------------------------------ proyek terakhir (layar awal)
    def _show_recent(self):
        self.welcome.set_recent(self.settings.get("recent_projects") or [],
                                self.settings.get("recent_opened") or {})

    def _add_recent(self, f):
        """Catat proyek yang baru dibuka / disimpan: naik ke urutan teratas (maks. 10 diingat)."""
        if not f:
            return
        import time
        f = os.path.abspath(f)
        key = os.path.normcase(f)
        lst = [p for p in (self.settings.get("recent_projects") or [])
               if os.path.normcase(os.path.abspath(p)) != key]
        self.settings["recent_projects"] = [f] + lst[:9]
        opened = {k: v for k, v in (self.settings.get("recent_opened") or {}).items()
                  if k in self.settings["recent_projects"]}
        opened[f] = time.time()
        self.settings["recent_opened"] = opened
        pipeline.save_settings(self.settings)
        self._show_recent()

    def _remove_recent(self, f):
        self.settings["recent_projects"] = [p for p in (self.settings.get("recent_projects") or []) if p != f]
        pipeline.save_settings(self.settings)
        self._show_recent()

    def _open_recent(self, f):
        if not Path(f).exists():
            QMessageBox.warning(self, APP_NAME, f"File proyek tidak ditemukan:\n{f}")
            self._remove_recent(f)
            return
        if self.project.pages and not self.confirm_unsaved():
            return
        self._load_project(f)

    def _mark_saved(self):
        self._saved_sig = self._project_sig()
        self._refresh_state()
        self._update_title()

    def _refresh_state(self):
        has = bool(self.project.pages)
        if self._saved_sig is None and has:
            self._saved_sig = self._project_sig()      # proyek baru dimuat = belum ada perubahan
        dirty = has and self._project_sig() != self._saved_sig
        if dirty != self._dirty:
            self._dirty = dirty
            if not getattr(self, "_save_anim", None):
                self.b_save.setIcon(icon("save_dirty" if dirty else "save"))
            self.b_save.setToolTip("Simpan proyek (Ctrl+S) · ada perubahan yang belum disimpan" if dirty
                                   else "Simpan proyek (Ctrl+S) · semua perubahan sudah tersimpan")
            self._update_title()
        if not getattr(self, "_save_anim", None):          # selama animasi simpan: biarkan tombol menyala
            self.b_save.setEnabled(dirty and not self.thread)
        p = self.page()
        h = self._hist(p) if p else {"undo": [], "redo": []}
        busy = bool(self.thread)
        # tombol yang butuh halaman: mati (redup) bila belum ada gambar yang dibuka
        n = len(self.project.pages)
        for w_ in (self.b_box, *self.tool_btns.values(), self.b_split):
            w_.setEnabled(has and not busy)
        self.brush_field.setEnabled(has and getattr(self, "tool", "select") in ("heal", "line"))
        self.b_line_color.setEnabled(has and getattr(self, "tool", "select") in ("line", "pen", "shape"))
        self.b_prev.setEnabled(has and self.cur > 0)
        self.b_next.setEnabled(has and 0 <= self.cur < n - 1)
        self.b_export.setEnabled(bool(self.project.pages) and not busy)
        self.b_skill.setEnabled(bool(self.project.pages) and not busy)
        self.b_undo.setEnabled(bool(h["undo"]) and not busy)
        self.b_redo.setEnabled(bool(h["redo"]) and not busy)
        self.b_undo.setToolTip(f"Undo (Ctrl+Z) · {len(h['undo'])} dari maks. {UNDO_LIMIT} langkah")
        self.b_redo.setToolTip(f"Redo (Ctrl+Y) · {len(h['redo'])} langkah")

    # ------------------------------------------------------------------ Spasi = tangan (geser gambar)
    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        t = ev.type()
        if t in (QEvent.KeyPress, QEvent.KeyRelease) and ev.key() == Qt.Key_Space:
            if not self._space_allowed():
                return False
            if not ev.isAutoRepeat():
                on = t == QEvent.KeyPress
                if on != PageCanvas.space_held:
                    for cv in (self.cv_src, self.cv_out):
                        cv.set_space(on)
                    if on:
                        self._space_msg = self.status_lbl.text()
                        self.status_lbl.setText("✋ Mode tangan: seret untuk menggeser gambar (lepas Spasi = kembali)")
                    else:
                        self.status_lbl.setText(getattr(self, "_space_msg", ""))
            return True              # jangan sampai Spasi menekan tombol yang sedang fokus
        if t == QEvent.WindowDeactivate and PageCanvas.space_held and obj is self:
            for cv in (self.cv_src, self.cv_out):
                cv.set_space(False)
        return super().eventFilter(obj, ev)

    def _space_allowed(self) -> bool:
        if not self.project.pages or QApplication.activeModalWidget() is not None:
            return False
        if QApplication.activeWindow() is not self:
            return False
        f = QApplication.focusWidget()
        from PySide6.QtWidgets import QLineEdit, QTextEdit
        if isinstance(f, NumField):
            return True                  # kolom angka tidak butuh spasi
        if isinstance(f, (QLineEdit, QPlainTextEdit, QTextEdit, QAbstractSpinBox)):
            return False                 # sedang mengetik: spasi = spasi biasa
        if isinstance(f, QComboBox) and f.isEditable():
            return False
        return True

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self._load_paths([u.toLocalFile() for u in e.mimeData().urls()])

    # ================================================================== halaman
    def open_page(self, i):
        self.cur = i
        self.sel = None
        self.b_box.setChecked(False)
        self.cv_src.set_draw_mode(False)
        self._show_current(fit=True)
        self._update_title()
        p = self.page()
        if (p and not self.thread and any(b.translation for b in p.blocks)
                and not (p.output_path and Path(p.output_path).exists())):
            self.log(f"[{p.name}] terjemahan ada tapi belum dirender — merender…")
            QTimer.singleShot(100, lambda: self.render_current(quiet=True))

    def _out_image(self, p):
        mode = self.out_mode.currentData()
        if mode == "bersih" and p.cleaned_path and Path(p.cleaned_path).exists():
            return p.cleaned_path, "BERSIH"
        if p.output_path and Path(p.output_path).exists():
            return p.output_path, "TERJEMAHAN"
        if p.cleaned_path and Path(p.cleaned_path).exists():
            return p.cleaned_path, "BERSIH"
        # belum diproses: tampilkan cermin gambar asli supaya selalu ada 2 gambar berdampingan
        return p.path, "PRATINJAU"

    def _show_current(self, fit=False):
        p = self.page()
        n = len(self.project.pages)
        self.page_lbl.setText(f"{self.cur + 1 if p else 0}/{n}")
        if not p:
            self.cv_src.set_page(None, [])
            self.cv_out.set_page(None, [])
            self.col_out.header.setText("TERJEMAHAN")
            self._fill_table()
            self._load_props(None)
            self.count_lbl.setText("0 balon")
            return
        z = self.cv_src.zoom()
        hs, vs = self.cv_src.horizontalScrollBar().value(), self.cv_src.verticalScrollBar().value()
        self.cv_src.set_page(p.path, p.blocks, fit=False)
        out, kind = self._out_image(p)
        self.cv_out.set_page(out, p.blocks, fit=False)
        self.col_out.header.setText({
            "TERJEMAHAN": "TERJEMAHAN",
            "BERSIH": "TERJEMAHAN · TEKS DIHAPUS",
            "PRATINJAU": "TERJEMAHAN · belum diproses — klik ⚡ Terjemahkan",
        }[kind])
        if fit:
            QTimer.singleShot(0, self._fit_both)
        else:
            self.cv_src.set_zoom(z)
            self.cv_out.set_zoom(z)
            for cv in (self.cv_src, self.cv_out):
                cv.horizontalScrollBar().setValue(hs)
                cv.verticalScrollBar().setValue(vs)
        self.count_lbl.setText(f"{len(p.blocks)} balon")
        self._fill_table()
        keep = self.sel if self.sel in p.blocks else None
        self.sel = keep
        self.multi = [m for m in self.multi if _has(p.blocks, m)] if keep else []
        if len(self.multi) < 2:
            self.multi = []
        for cv in (self.cv_src, self.cv_out):
            cv.select_block(keep, ensure_visible=False, multi=self.multi)
        self._sync_table_sel()
        self._load_props(keep)

    # ================================================================== daftar balon (tabel)
    def _fill_table(self):
        p = self.page()
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if p:
            for i, b in enumerate(p.blocks):
                self.table.insertRow(i)
                n = QTableWidgetItem(str(i + 1))
                n.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(i, 0, n)
                self.table.setItem(i, 1, QTableWidgetItem(b.source))
                self.table.setItem(i, 2, QTableWidgetItem(b.translation))
            self.table.resizeRowsToContents()
        self.table.blockSignals(False)

    def _on_table_edit(self, item):
        p = self.page()
        if not p or item.row() >= len(p.blocks):
            return
        b = p.blocks[item.row()]
        self._snap(("text", b.id))
        if item.column() == 1:
            b.source = item.text()
        elif item.column() == 2:
            b.translation = item.text()
            self._schedule_render()
        if b is self.sel:
            self._load_props(b)

    def _on_table_select(self):
        p = self.page()
        if not p:
            return
        rows = sorted({i.row() for i in self.table.selectedItems() if 0 <= i.row() < len(p.blocks)})
        if not rows:
            return
        r = self.table.currentRow()
        prim = p.blocks[r] if r in rows else p.blocks[rows[-1]]
        many = [p.blocks[i] for i in rows] if len(rows) > 1 else None
        self._select(prim, from_table=True, multi=many)

    def _sync_table_sel(self):
        """Sorot baris tabel untuk semua balon terpilih."""
        p = self.page()
        if not p:
            return
        from PySide6.QtCore import QItemSelection, QItemSelectionModel
        sm = self.table.selectionModel()
        self.table.blockSignals(True)
        sm.blockSignals(True)
        self.table.clearSelection()
        sel = QItemSelection()
        for b in (self.multi or ([self.sel] if self.sel else [])):
            r = _idx(p.blocks, b)
            if r >= 0:
                sel.select(self.table.model().index(r, 0), self.table.model().index(r, 2))
        sm.select(sel, QItemSelectionModel.Select)
        if _idx(p.blocks, self.sel) >= 0:
            sm.setCurrentIndex(self.table.model().index(_idx(p.blocks, self.sel), 0), QItemSelectionModel.NoUpdate)
        sm.blockSignals(False)
        self.table.blockSignals(False)

    def _targets(self) -> list:
        """Balon yang diubah oleh panel properti: semua yang dipilih (Ctrl+klik), atau balon aktif saja."""
        p = self.page()
        if not p or not self.sel:
            return []
        many = [m for m in self.multi if _has(p.blocks, m)]
        return many if len(many) > 1 else ([self.sel] if _has(p.blocks, self.sel) else [])

    def _on_canvas_toggle(self, block):
        """Ctrl+klik balon: tambahkan ke / lepaskan dari pilihan."""
        p = self.page()
        if not p or not _has(p.blocks, block):
            return
        cur = [m for m in (self.multi or ([self.sel] if self.sel else [])) if _has(p.blocks, m)]
        if any(m is block for m in cur):
            cur = [m for m in cur if m is not block]
            prim = self.sel if self.sel is not block else (cur[-1] if cur else None)
        else:
            cur.append(block)
            prim = block
        if self.tabs.currentIndex() == 2:
            self.tabs.setCurrentIndex(0)
        self._select(prim, from_canvas=True, multi=cur if len(cur) > 1 else None)
        if prim is None:
            self.table.clearSelection()
        elif len(cur) > 1:
            self.status_lbl.setText(f"{len(cur)} balon dipilih · ubahan di panel kanan berlaku ke semuanya "
                                    "· Ctrl+klik lagi untuk melepas")

    # ================================================================== seleksi & properti
    def _select(self, b, from_table=False, from_canvas=False, multi=None):
        self.sel = b
        self.multi = list(multi) if (b is not None and multi and len(multi) > 1) else []
        for cv in (self.cv_src, self.cv_out):      # sorot balon yang sama di kedua sisi
            cv.select_block(b, ensure_visible=not from_canvas and not self.multi, multi=self.multi)
        if b and not from_table:
            self._sync_table_sel()
        self._load_props(b)

    def _on_canvas_select(self, block):
        self._select(block, from_canvas=True)
        if block is not None and self.tabs.currentIndex() == 2:
            self.tabs.setCurrentIndex(0)
        if block is None:
            self.table.clearSelection()

    def _focus_translation(self, block):
        self._select(block)
        self.tabs.setCurrentIndex(0)
        self.e_tr.setFocus()
        self.e_tr.selectAll()

    def _load_props(self, b):
        self._loading = True
        on = b is not None
        self.props_hint.setVisible(not on)
        for s in self.sections:
            s.setEnabled(on)
        if b:
            idx = self.page().blocks.index(b) + 1 if self.page() and b in self.page().blocks else ""
            n = len(self._targets())
            self.sections[0].btn.setText(f"  TERJEMAHAN · BALON #{idx}" + (f"  (+{n - 1} dipilih)" if n > 1 else ""))
            self.multi_bar.setVisible(n > 1)
            if n > 1:
                self.multi_lbl.setText(f"<b>{n} balon dipilih</b> — ubahan gaya berlaku ke semua")
            if self.e_src.toPlainText() != b.source:
                self.e_src.setPlainText(b.source)
            if self.e_tr.toPlainText() != b.translation:
                self.e_tr.setPlainText(b.translation)
            i = self.p_font.findData(b.font)
            if i < 0 and b.font:
                self.p_font.addItem(typeset.font_name(b.font), b.font)
                i = self.p_font.count() - 1
            self.p_font.setCurrentIndex(max(0, i))
            self.p_size.setValue(b.font_size)
            self._update_fit_text(b)
            self.p_bold.setChecked(b.bold)
            for n, btn in enumerate(self.p_presets, 1):
                btn.setChecked(b.preset == n)
            self.p_ital.setChecked(b.italic if b.italic is not None else bool(self.settings.get("italic", True)))
            for k, btn in self.p_al.items():
                btn.setChecked(k == b.align)
            self._color_btn(self.p_color, b.color)
            self._grad_btn(b)
            self.p_stroke.setValue(b.stroke_width)
            self.p_lsp.setValue(float(b.line_spacing or self._default_lsp()))
            self.p_ls.setValue(float(b.letter_spacing or 0))
            self.p_rot.setValue(int(round(b.rotation or 0)))
            self.p_lines.setValue(int(getattr(b, "max_lines", 0) or 0))
            for k, btn in self.p_case.items():
                btn.setChecked(b.case == k)
            self._color_btn(self.p_stroke_color, b.stroke_color)
            self.p_kind.setCurrentIndex(max(0, self.p_kind.findData(b.kind)))
            self.p_clean.setChecked(b.clean)
            self.b_title.setVisible(b.kind == "title")
        else:
            self.sections[0].btn.setText("  TERJEMAHAN")
            self.multi_bar.setVisible(False)
            self.e_src.clear()
            self.e_tr.clear()
            # tampilkan nilai netral (bukan batas minimum seperti -180° / -10)
            self.p_size.setSpecialValueText("Auto")
            self.p_size.setValue(0)
            self.p_lsp.setValue(self._default_lsp())
            self.p_ls.setValue(0)
            self.p_rot.setValue(0)
            self.p_lines.setValue(0)
            self.p_stroke.setValue(0)
            for btn in (self.p_color, self.p_color2, self.p_stroke_color):
                btn.setStyleSheet("")
        self._loading = False

    @staticmethod
    def _color_btn(btn, color):
        btn.setText("")
        btn.setToolTip(f"{btn.toolTip().split('  ·')[0]}  ·  {color.upper()}")
        btn.setStyleSheet(f"background:{color}; border:1px solid #4b5470; border-radius:4px;")

    def _on_src_text(self):
        if self._loading or not self.sel:
            return
        self._snap(("text", self.sel.id))
        self.sel.source = self.e_src.toPlainText()
        self._sync_table_row(self.sel)

    def _on_tr_text(self):
        if self._loading or not self.sel:
            return
        self._snap(("text", self.sel.id))
        self.sel.translation = self.e_tr.toPlainText()
        self._sync_table_row(self.sel)
        self._schedule_render()

    def _sync_table_row(self, b):
        p = self.page()
        if not p or b not in p.blocks:
            return
        r = p.blocks.index(b)
        self.table.blockSignals(True)
        self.table.item(r, 1).setText(b.source)
        self.table.item(r, 2).setText(b.translation)
        self.table.blockSignals(False)

    def _set_align(self, k):
        if self.sel:
            self._snap()
            for t in self._targets():
                t.align = k
            for kk, btn in self.p_al.items():
                btn.setChecked(kk == k)
            self._schedule_render()

    def _match_font(self):
        b, p = self.sel, self.page()
        if not b or not p:
            return
        from core import detector, fontmatch
        rect = b.text_rect if b.text_rect else [b.x, b.y, b.w, b.h]
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.status_lbl.setText("Mencari font yang mirip… (pertama kali agak lama)")
        QApplication.processEvents()
        try:
            img = detector.load_image(p.path)
            res = fontmatch.best_font(img, rect, b.src_h or int(b.h * 0.3), top=3,
                                      include_system=bool(self.settings.get("font_match_system", True)),
                                      online=bool(self.settings.get("font_match_online", True)),
                                      log=self.log)
        except Exception as e:
            res = []
            self.log(f"Cocokkan font gagal: {e}")
        finally:
            QApplication.restoreOverrideCursor()
        if not res:
            self.status_lbl.setText("Tidak ada font yang cocok ditemukan")
            return
        self._snap()
        path = res[0][0]
        b.font = path
        i = self.p_font.findData(path)
        if i < 0:
            self.p_font.addItem(typeset.font_name(path), path)
            i = self.p_font.count() - 1
        self._loading = True
        self.p_font.setCurrentIndex(i)
        self._loading = False
        names = ", ".join(typeset.font_name(p_) for p_, _ in res)
        self.status_lbl.setText(f"Font: {typeset.font_name(path)}")
        self.log(f"Font paling mirip: {names}")
        self._schedule_render()

    def make_title(self):
        """Ganti logo judul seri di halaman ini dengan logo terjemahan bergaya mirip."""
        p = self.page()
        if not p or self.thread:
            return
        from PySide6.QtWidgets import QInputDialog
        cur = self.project.series_title or self.settings.get("last_series_title", "")
        text, ok = QInputDialog.getText(
            self, "Logo judul seri",
            "Judul seri dalam bahasa tujuan (dipakai juga untuk chapter lain di proyek ini).\n"
            "Kata sambung (yang, di, setelah, of, the…) otomatis dibuat kecil.", text=cur)
        text = (text or "").strip()
        if not ok or not text:
            return
        self.project.series_title = text
        self.settings["last_series_title"] = text
        try:
            pipeline.save_settings(self.settings)
        except Exception:
            pass
        proj, st, i = self.project, dict(self.settings), self.cur
        self._snap()

        def job(w: Worker):
            from core import detector
            img = detector.load_image(p.path)
            b = pipeline.add_title_block(img, p, proj, st, strict=False)
            if b is None:
                w.log.emit("Logo judul tidak ditemukan di halaman ini. Gambar kotak manual (B) di atas "
                           "logo, lalu ubah jenisnya ke 'Logo judul seri'.")
                return
            w.log.emit(f"Logo judul: {text}")
            pipeline.step_render(p, proj, st, recalc_clean=True)
            w.page_updated.emit(i)

        self._start(job, f"Logo judul · {p.name}")

    def _default_lsp(self) -> float:
        return round(float(self.settings.get("line_spacing", 1.2) or 1.2), 2)

    def _update_fit_text(self, b=None):
        """Ukuran Auto ditampilkan dengan angka hasil render terakhir, mis. "Auto · 24"."""
        b = b or self.sel
        if not b:
            return
        self.p_size.setSpecialValueText(f"Auto · {b.fit_size}" if b.fit_size else "Auto")

    PROP_FIELDS = ("font", "font_size", "bold", "stroke_width", "line_spacing", "letter_spacing", "rotation",
                   "max_lines", "kind", "clean")

    def _on_prop_change(self, *_):
        b = self.sel
        if self._loading or not b:
            return
        targets = self._targets()
        before = {f: getattr(b, f, None) for f in self.PROP_FIELDS}
        self._apply_props(b)
        changed = {f: getattr(b, f, None) for f in self.PROP_FIELDS if getattr(b, f, None) != before[f]}
        others = [t for t in targets if t is not b]
        if changed and others:            # pilihan ganda: hanya nilai yang barusan diubah yang disalin
            p = self.page()
            for t in others:
                old = (t.clean, t.kind)
                for f, val in changed.items():
                    setattr(t, f, val)
                if (t.clean, t.kind) != old and p:
                    self.need_clean.add(p.path)
            self._schedule_render()

    def _apply_props(self, b):
        self._snap(("prop", b.id))
        old = (b.clean, b.kind)
        new_font = self.p_font.currentData() or ""
        if new_font != b.font and b.font_cat and self.settings.get("font_match_all", True):
            # font yang dipilih manual diingat untuk golongan teks ini di halaman berikutnya
            self.project.font_memory[b.font_cat] = new_font
            from core.pipeline import FONT_CAT_LABEL
            self.log(f"Font “{typeset.font_name(new_font) if new_font else 'default'}” diingat untuk "
                     f"{FONT_CAT_LABEL.get(b.font_cat, b.font_cat)} di halaman berikutnya.")
        b.font = new_font
        size = self.p_size.value()
        if b.font_size == 0 and size == 1 and b.fit_size:
            size = b.fit_size + 1          # naik dari "Auto": mulai dari ukuran yang sedang tampil
            self._loading = True
            self.p_size.setValue(size)
            self._loading = False
        b.font_size = size
        b.bold = self.p_bold.isChecked()
        b.stroke_width = self.p_stroke.value()
        lsp = round(self.p_lsp.value(), 2)
        # tetap "ikut default" bila nilainya tidak diubah
        b.line_spacing = 0.0 if (not b.line_spacing and abs(lsp - self._default_lsp()) < 1e-6) else lsp
        b.letter_spacing = round(self.p_ls.value(), 1)
        b.rotation = float(self.p_rot.value())
        b.max_lines = int(self.p_lines.value())
        b.kind = self.p_kind.currentData()
        b.clean = self.p_clean.isChecked()
        self.b_title.setVisible(b.kind == "title")
        if b.kind == "title" and old[1] != "title":       # baru dijadikan kotak judul -> buka pembuat judul
            b.source = b.source or "[logo judul]"
            QTimer.singleShot(0, lambda b=b: self.edit_title(b))
        if (b.clean, b.kind) != old:
            self.need_clean.add(self.page().path)
            for cv in (self.cv_src, self.cv_out):
                for box in cv.boxes:
                    box.refresh_style()
        self._schedule_render()

    def _step_lines(self, d):
        b = self.sel
        if not b:
            return
        cur = int(getattr(b, "max_lines", 0) or 0)
        if not cur:      # dari Auto: mulai dari jumlah baris yang sedang tampil
            cur = max(1, self._shown_lines(b) or 1)
        self.p_lines.setValue(max(1, min(20, cur + d)), emit=True)

    @staticmethod
    def _shown_lines(b) -> int:
        """Jumlah baris yang tampil pada render terakhir."""
        return int(getattr(b, "_fit_lines", 0) or 0)

    def _set_case(self, k):
        b = self.sel
        if not b:
            return
        self._snap()
        b.case = None if b.case == k else k          # klik lagi = kembali ikut default
        for t in self._targets():
            t.case = b.case
        for kk, btn in self.p_case.items():
            btn.setChecked(b.case == kk)
        self._schedule_render()

    def _nudge(self, dx, dy):
        b = self.sel
        if not b:
            return
        self._snap(("nudge", b.id))
        step = 10 if QApplication.keyboardModifiers() & Qt.ShiftModifier else 2
        for t in self._targets() or [b]:
            if not dx and not dy:
                t.dx = t.dy = 0
            else:
                t.dx = int(t.dx or 0) + dx * step
                t.dy = int(t.dy or 0) + dy * step
        self._schedule_render()

    def _update_preset_tips(self):
        case_txt = {"upper": "KAPITAL", "lower": "huruf kecil", "none": "huruf biasa"}
        for n, (btn, p) in enumerate(zip(self.p_presets, pipeline.presets(self.settings)), 1):
            font = typeset.font_name(p["font"]) if p["font"] else "font default"
            style = ", ".join(x for x in ("tebal" if p["bold"] else "", "miring" if p["italic"] else "",
                                         case_txt.get(p["case"], "")) if x)
            btn.setToolTip(f"Preset {n}{' (default)' if n == 1 else ''}: {font} · {style}\n"
                           f"Pintasan: {SC.current(self.settings).get(f'preset{n}', '')} · ubah di Pengaturan → Teks")

    def apply_preset(self, n: int):
        """Terapkan preset teks ke balon terpilih (tombol 1–5)."""
        b = self.sel
        if not b:
            self.status_lbl.setText(f"Pilih balon dulu untuk menerapkan Preset {n}")
            return
        self._snap()
        ts = self._targets() or [b]
        for t in ts:
            pipeline.apply_preset(t, self.settings, n)
        self._load_props(b)
        self._schedule_render()
        self.status_lbl.setText(f"Preset {n} diterapkan ke {len(ts)} balon" if len(ts) > 1 else
                                f"Preset {n} diterapkan ke balon #{self.page().blocks.index(b) + 1}")

    def _on_italic(self, on):
        if self._loading or not self.sel:
            return
        self._snap()
        for t in self._targets():
            t.italic = bool(on)      # pilihan khusus balon ini
        self._schedule_render()

    def _pick_color(self, attr):
        b = self.sel
        if not b:
            return
        c = QColorDialog.getColor(QColor(getattr(b, attr) or b.color), self)
        if c.isValid():
            self._snap()
            for t in self._targets() or [b]:
                setattr(t, attr, c.name())
            if attr == "color2":
                self._grad_btn(b)
            else:
                self._color_btn(self.p_color if attr == "color" else self.p_stroke_color, c.name())
            self._schedule_render()

    def _pick_from_source(self):
        b, p = self.sel, self.page()
        if not b or not p:
            return
        from core import detector, textstyle
        try:
            img = detector.load_image(p.path)
        except Exception as e:
            self.log(f"Gagal membaca gambar: {e}")
            return
        self._snap()
        for t in self._targets():
            if t is not b:
                textstyle.apply(img, t)      # pilihan ganda: tiap balon ambil warna aslinya sendiri
        old = (b.color, b.color2, b.stroke_color, b.stroke_width)
        if not textstyle.apply(img, b):
            self.status_lbl.setText("Warna teks asli tidak terbaca di kotak ini")
            return
        self._load_props(b)
        if (b.color, b.color2, b.stroke_color, b.stroke_width) != old:
            desc = b.color + (f" → {b.color2}" if b.color2 else "")
            if b.stroke_width:
                desc += f" · tepi {b.stroke_color} {b.stroke_width}px"
            self.status_lbl.setText(f"Warna diambil: {desc}")
            self._schedule_render()

    def _gradient_dialog(self):
        b = self.sel
        if not b:
            return
        from .gradient_dialog import GradientDialog
        self._snap()

        others = [t for t in self._targets() if t is not b]

        def changed():
            for t in others:          # pilihan ganda: gradasi yang sama untuk semua
                for f in ("color", "color2", "grad_type", "grad_angle", "grad_pos", "grad_soft"):
                    setattr(t, f, getattr(b, f, None))
            self._grad_btn(b)
            self._color_btn(self.p_color, b.color)
            self._schedule_render()
        d = GradientDialog(b, changed, self)
        d.finished.connect(lambda *_: changed())
        changed()
        d.show()
        self._grad_dlg = d          # simpan referensi (dialog non-modal)

    def _grad_btn(self, b):
        if b.color2:
            from core.gradient import css_preview
            self._color_btn(self.p_color2, b.color2)
            css = css_preview(b.grad_type or "linear", b.grad_angle if b.grad_angle is not None else 90,
                              b.color, b.color2, b.grad_pos if b.grad_pos is not None else 0.5,
                              b.grad_soft if b.grad_soft is not None else 1.0)
            self.p_color2.setStyleSheet(f"background: {css}; border:1px solid #4b5470; border-radius:4px;")
        else:
            self.p_color2.setText("")
            self.p_color2.setStyleSheet("background: transparent; border:1px dashed #4b5470; border-radius:4px;")
        self.p_grad_off.setEnabled(bool(b.color2))

    def _clear_gradient(self):
        b = self.sel
        if not b or not b.color2:
            return
        self._snap()
        for t in self._targets() or [b]:
            t.color2 = ""
        self._grad_btn(b)
        self._schedule_render()

    # ================================================================== edit kotak
    def _on_edit_started(self, block):
        self._pending_snap = self._state()

    def _on_geom_changed(self, block):
        p = self.page()
        if getattr(self, "_pending_snap", None) is not None:
            self._push_undo(self._pending_snap)
            self._pending_snap = None
        for cv in (self.cv_src, self.cv_out):
            cv.reload_boxes()
        if p:
            self.need_clean.add(p.path)
            self._schedule_render()

    def _add_box(self, rect: QRectF):
        p = self.page()
        if not p:
            return
        b = TextBlock(x=int(rect.x()), y=int(rect.y()), w=int(rect.width()), h=int(rect.height()),
                      kind="free", stroke_width=int(self.settings.get("default_stroke", 0)))
        if getattr(self, "_title_box", False):          # Skill -> Kotak judul
            self._title_box = False
            self._snap()
            b.kind, b.source, b.text_rect = "title", "[logo judul]", [b.x, b.y, b.w, b.h]
            p.blocks.append(b)
            self.b_box.setChecked(False)
            self.cv_src.set_draw_mode(False)
            self.sel = b
            self._show_current()
            self.tabs.setCurrentIndex(0)
            QTimer.singleShot(0, lambda: self.edit_title(b))
            return
        self._snap()
        try:
            from core import detector, inpaint
            inpaint.auto_style(detector.load_image(p.path), b)   # huruf putih -> putih + stroke hitam
        except Exception:
            pass
        p.blocks.append(b)
        self.need_clean.add(p.path)
        self.b_box.setChecked(False)
        self.cv_src.set_draw_mode(False)
        self.sel = b
        self._show_current()
        self.tabs.setCurrentIndex(0)
        mode = self.settings.get("box_mode", "box")
        if mode == "box":
            self.log("Kotak baru ditambahkan. Ketik teksnya, atau tekan 'OCR ulang' untuk membaca teksnya.")
        elif mode == "ocr":
            self.log("Kotak baru ditambahkan — membaca teksnya…")
            self._block_job("ocr_only")
        else:
            self.log("Kotak baru ditambahkan — membaca & menerjemahkan teksnya…")
            self._block_job("ocr")

    def _set_box_mode(self, action):
        mode = action.data() or "box"
        self.settings["box_mode"] = mode
        pipeline.save_settings(self.settings)
        self.status_lbl.setText("Kotak manual: " + dict(BOX_MODES).get(mode, "").lower())

    # ================================================================== alat sunting gambar
    def set_tool(self, tool):
        self.tool = tool
        for t, b in self.tool_btns.items():
            b.setChecked(t == tool)
        if tool != "select" and self.b_box.isChecked():
            self.b_box.setChecked(False)
            self.cv_src.set_draw_mode(False)
        if tool in self._tool_sizes:
            self.brush_field.setValue(self._tool_sizes[tool])
        for cv in (self.cv_src, self.cv_out):
            cv.set_tool(tool)
            cv.line_color = self.line_color
            cv.set_brush(int(self.brush_field.value()))
        self.brush_field.setEnabled(tool in ("heal", "line"))
        self.b_line_color.setEnabled(tool in ("line", "pen", "shape"))
        hints = {"select": "Pilih / geser kotak teks.",
                 "pen": "Pen: klik titik-titik di sekeliling area. Klik titik awal / klik kanan / Enter = selesai, "
                        "Backspace = hapus titik terakhir, Esc = batal.",
                 "shape": f"Shape ({'oval' if self.cv_src.shape_kind == 'ellipse' else 'kotak'}): seret di gambar. "
                          "Shift = persegi/lingkaran. Tekan A lagi untuk ganti bentuk.",
                 "heal": "Healing brush: sapukan di atas noda / sisa teks / objek. [ ] = ukuran kuas.",
                 "patch": "Patch: seret melingkari area yang belum rapi. AI mencari area serupa di halaman "
                          "dan menambalnya. (Atau pakai Pen lalu pilih 'Tambal dengan area serupa'.)",
                 "line": "Garis: klik = tambah titik, seret = gambar bebas (Shift = lurus). Hasilnya pratinjau "
                         "putus-putus yang bisa diedit; Enter / tombol 'Jadikan garis' = jadi garis."}
        self.status_lbl.setText(hints.get(tool, ""))

    def _shape_key(self):
        if getattr(self, "tool", "select") == "shape":
            kind = "ellipse" if self.cv_src.shape_kind == "rect" else "rect"
            for cv in (self.cv_src, self.cv_out):
                cv.shape_kind = kind
        self.set_tool("shape")

    def _brush_step(self, f):
        v = int(round(self.brush_field.value() * f))
        if v == self.brush_field.value():
            v += 1 if f > 1 else -1
        self.brush_field.setValue(v, emit=True)

    def _add_edit(self, e: dict, label: str):
        p = self.page()
        if not p:
            return
        self._snap()
        p.edits = list(p.edits or []) + [e]
        self.log(label)
        self._schedule_render(now=True)

    def _on_brush_size(self, v):
        t = getattr(self, "tool", "select")
        if t in self._tool_sizes:
            self._tool_sizes[t] = int(v)
            if t == "line":
                self.settings["line_width"] = int(v)
        for cv in (self.cv_src, self.cv_out):
            cv.set_brush(int(v))

    def _paint_line_swatch(self):
        self.b_line_color.setStyleSheet(f"QToolButton#lineSwatch {{ background: {self.line_color}; "
                                        "border: 2px solid #4b5470; border-radius: 5px; }"
                                        "QToolButton#lineSwatch:disabled { background: #2a3142; border-color: #2a3142; }")

    def _pick_line_color(self):
        c = QColorDialog.getColor(QColor(self.line_color), self, "Warna garis")
        if c.isValid():
            self.line_color = c.name()
            self.settings["line_color"] = self.line_color
            pipeline.save_settings(self.settings)
            for cv in (self.cv_src, self.cv_out):
                cv.line_color = self.line_color
            self._paint_line_swatch()

    # ------------------------------------------------------------------ pratinjau garis (alat garis)
    def _draft_canvas(self, cv=None):
        if cv is not None and cv.draft["pts"]:
            return cv
        for c in (self.cv_src, self.cv_out):
            if c.draft["pts"]:
                return c
        return None

    def _on_draft_changed(self, cv, on):
        has = self._draft_canvas() is not None
        self._a_line_ok.setVisible(has)
        self._a_line_cancel.setVisible(has)
        c = self._draft_canvas()
        self.b_line_ok.setEnabled(bool(c and c.has_draft()))
        if has and getattr(self, "tool", "") == "line":
            self.status_lbl.setText("Pratinjau garis: seret titik untuk mengedit · Ctrl+klik / klik 2x garis = "
                                    "tambah titik · klik 2x / Alt+klik titik = hapus · klik titik awal = tutup · "
                                    "Enter = jadikan garis · klik kanan = pilihan")

    def _fill_draft_menu(self, m, cv):
        m.clear()
        c = self._draft_canvas(cv)
        if not c:
            return
        closed = c.draft["closed"]
        ok = c.has_draft()
        a = m.addAction(icon("line"), "Jadikan garis" + ("  (tertutup)" if closed else ""),
                        lambda: self._commit_draft(c, "auto"))
        a.setEnabled(ok)
        if len(c.draft["pts"]) >= 3:
            m.addAction(icon("line"), "Jadikan balon: isi putih + garis tepi",
                        lambda: self._commit_draft(c, "bubble"))
            m.addAction("Jadikan area isi putih (tanpa garis)", lambda: self._commit_draft(c, "fill"))
        m.addSeparator()
        a_s = m.addAction("Garis melengkung halus")
        a_s.setCheckable(True)
        a_s.setChecked(c.draft["smooth"])
        a_s.toggled.connect(lambda v: c.set_draft_option("smooth", v))
        if len(c.draft["pts"]) >= 3:
            a_c = m.addAction("Tutup bentuk (sambung ke titik awal)")
            a_c.setCheckable(True)
            a_c.setChecked(closed)
            a_c.toggled.connect(lambda v: c.set_draft_option("closed", v))
        m.addSeparator()
        m.addAction(icon("close"), "Hapus pratinjau", lambda: self._commit_draft(c, "cancel"))

    def _draft_menu(self, cv, pos):
        if pos == "commit":
            self._commit_draft(cv, "auto")
            return
        m = QMenu(self)
        self._fill_draft_menu(m, cv)
        m.exec(pos)

    def _commit_draft(self, cv, how):
        c = self._draft_canvas(cv)
        if not c:
            return
        if how == "cancel":
            c.clear_draft()
            return
        if not c.has_draft() and how == "auto":
            return
        d = c.take_draft()
        w, col = self._line_w(), self.line_color
        closed = d["closed"] or how in ("bubble", "fill")
        if how == "fill":
            from core.edits import spline
            poly = [[int(round(x)), int(round(y))] for x, y in spline(d["pts"], True, d["smooth"])]
            self._add_edit({"op": "fill", "poly": poly, "color": "#FFFFFF"}, "Area diisi putih")
        elif closed:
            self._add_edit({"op": "outline", "poly": d["pts"], "w": w, "color": col, "smooth": d["smooth"],
                            "fill": "#FFFFFF" if how == "bubble" else ""},
                           "Balon digambar" if how == "bubble" else "Garis tepi digambar")
        else:
            self._add_edit({"op": "stroke", "pts": d["pts"], "w": w, "color": col, "smooth": d["smooth"]},
                           "Garis digambar")
        pipeline.save_settings(self.settings)

    def _line_w(self) -> int:
        return int(self._tool_sizes.get("line", 3))

    def _on_line(self, pts, w):
        if len(pts) and self.page():
            pipeline.save_settings(self.settings)
            self._add_edit({"op": "stroke", "pts": pts, "w": int(w), "color": self.line_color},
                           "Garis digambar")

    def _on_heal(self, pts, r):
        if len(pts) and self.page():
            self._add_edit({"op": "heal", "pts": pts, "r": int(r)}, "Healing brush: area dibuat ulang AI")

    def _on_patch(self, pts):
        if len(pts) >= 3 and self.page():
            self._add_edit({"op": "patch", "poly": pts}, "Area ditambal dengan area serupa (Patch)")

    def _on_region(self, pts, screen_pos):
        p = self.page()
        if not p or len(pts) < 3:
            return
        from PySide6.QtGui import QCursor
        m = QMenu(self)
        a_patch = m.addAction(icon("patch"), "Tambal dengan area serupa (Patch)  — cari latar yang sama")
        a_ai = m.addAction(icon("heal"), "Hapus area dengan AI (LaMa)  — buat ulang latar")
        a_white = m.addAction("Isi putih")
        a_col = m.addAction("Isi warna…")
        a_pick = m.addAction("Isi warna latar di sekitarnya")
        a_rest = m.addAction("Kembalikan gambar asli di area ini")
        m.addSeparator()
        a_bubble = m.addAction(icon("line"), "Gambar balon: isi putih + garis tepi")
        a_outline = m.addAction(icon("line"), "Gambar garis tepi saja")
        m.addSeparator()
        a_box = m.addAction(icon("box"), "Buat kotak teks di area ini")
        a_shape = m.addAction("Jadikan bentuk balon yang dipilih") if self.sel else None
        m.addSeparator()
        m.addAction("Batal")
        act = m.exec(screen_pos or QCursor.pos())
        if act is None:
            return
        if act is a_patch:
            self._add_edit({"op": "patch", "poly": pts}, "Area ditambal dengan area serupa (Patch)")
        elif act is a_ai:
            self._add_edit({"op": "erase", "poly": pts}, "Area dihapus, latar dibuat ulang AI")
        elif act is a_white:
            self._add_edit({"op": "fill", "poly": pts, "color": "#FFFFFF"}, "Area diisi putih")
        elif act is a_col:
            c = QColorDialog.getColor(QColor("#FFFFFF"), self)
            if c.isValid():
                self._add_edit({"op": "fill", "poly": pts, "color": c.name()}, f"Area diisi {c.name()}")
        elif act is a_pick:
            self._add_edit({"op": "fill", "poly": pts, "color": self._ring_color(pts)}, "Area diisi warna latar")
        elif act in (a_bubble, a_outline):
            e = {"op": "outline", "poly": pts, "w": self._line_w(), "color": self.line_color,
                 "fill": "#FFFFFF" if act is a_bubble else ""}
            self._add_edit(e, "Balon digambar ulang" if act is a_bubble else "Garis tepi digambar")
        elif act is a_rest:
            self._add_edit({"op": "restore", "poly": pts}, "Gambar asli dikembalikan di area")
        elif act is a_box:
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            self._add_box(QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
        elif a_shape is not None and act is a_shape and self.sel:
            self._snap()
            b = self.sel
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            b.x, b.y, b.w, b.h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
            b.kind = "bubble"
            b.mask_poly = [list(q) for q in pts]
            self.need_clean.add(p.path)
            self._show_current()
            self._schedule_render(now=True)

    def _ring_color(self, pts) -> str:
        import numpy as np
        import cv2
        from core import detector
        p = self.page()
        img = detector.load_image(p.cleaned_path if p.cleaned_path and Path(p.cleaned_path).exists() else p.path)
        m = np.zeros(img.shape[:2], np.uint8)
        cv2.fillPoly(m, [np.array(pts, np.int32)], 255)
        ring = cv2.dilate(m, np.ones((9, 9), np.uint8)) & ~m
        vals = img[ring > 0]
        if not len(vals):
            return "#FFFFFF"
        b, g, r = np.median(vals, axis=0).astype(int)
        return f"#{r:02X}{g:02X}{b:02X}"

    def toggle_draw(self):
        on = self.b_box.isChecked()
        if on and getattr(self, "tool", "select") != "select":
            self.set_tool("select")
            self.b_box.setChecked(True)
        self.cv_src.set_draw_mode(on)
        if on:
            self.status_lbl.setText("Seret di gambar ASLI untuk membuat kotak teks baru.")

    def delete_selected(self):
        p, b = self.page(), self.sel
        if p and b in (p.blocks if p else []):
            self._snap()
            ts = self._targets() or [b]
            p.blocks[:] = [x for x in p.blocks if not _has(ts, x)]
            self.sel = None
            self.multi = []
            self.need_clean.add(p.path)
            self._show_current()
            self._schedule_render()

    # ================================================================== undo / redo
    def _hist(self, page):
        if not hasattr(self, "_history"):
            self._history = {}
        return self._history.setdefault(page.path, {"undo": [], "redo": []})

    def _state(self, page=None):
        page = page or self.page()
        if not page:
            return None
        import copy
        return {"blocks": [b.to_dict() for b in page.blocks], "edits": copy.deepcopy(page.edits or [])}

    def _push_undo(self, state, page=None):
        page = page or self.page()
        if page is None or state is None:
            return
        h = self._hist(page)
        if h["undo"] and h["undo"][-1] == state:
            return
        h["undo"].append(state)
        del h["undo"][:-UNDO_LIMIT]   # simpan maks. 5 langkah per halaman
        h["redo"].clear()

    def _snap(self, key=None, page=None):
        """Simpan keadaan SEBELUM perubahan. Ketikan/geser angka beruntun pada balon yang sama
        digabung jadi satu langkah undo (selama jedanya < 1,5 detik)."""
        import time
        page = page or self.page()
        if page is None:
            return
        now = time.monotonic()
        if key is not None and key == getattr(self, "_snap_key", None) and now - self._snap_t < 1.5:
            self._snap_t = now
            return
        self._snap_key, self._snap_t = key, now
        self._push_undo(self._state(page), page)

    def _restore(self, state):
        p = self.page()
        sel_id = self.sel.id if self.sel else None
        if isinstance(state, dict):
            p.blocks = [TextBlock.from_dict(d) for d in state.get("blocks", [])]
            p.edits = list(state.get("edits", []))
        else:
            p.blocks = [TextBlock.from_dict(d) for d in state]
        self.sel = next((b for b in p.blocks if b.id == sel_id), None)
        self.need_clean.add(p.path)
        self._snap_key = None
        self._show_current()
        self._schedule_render()

    def undo(self):
        p = self.page()
        if not p or self.thread:
            return
        h = self._hist(p)
        if not h["undo"]:
            self.status_lbl.setText("Tidak ada yang bisa di-undo")
            return
        h["redo"].append(self._state())
        del h["redo"][:-UNDO_LIMIT]
        self._restore(h["undo"].pop())
        self.status_lbl.setText(f"Undo  ·  {len(h['undo'])} langkah tersisa")
        self._refresh_state()

    def redo(self):
        p = self.page()
        if not p or self.thread:
            return
        h = self._hist(p)
        if not h["redo"]:
            self.status_lbl.setText("Tidak ada yang bisa di-redo")
            return
        h["undo"].append(self._state())
        del h["undo"][:-UNDO_LIMIT]
        self._restore(h["redo"].pop())
        self.status_lbl.setText(f"Redo  ·  {len(h['redo'])} langkah tersisa")
        self._refresh_state()

    # ================================================================== render otomatis
    def _schedule_render(self, now: bool = False):
        p = self.page()
        if now and p:                 # suntingan gambar: tampilkan hasilnya segera
            self._auto_render()
            return
        # hanya kalau halaman ini sudah pernah dirender (ada gambar bersih)
        if p and p.cleaned_path and Path(p.cleaned_path).exists():
            self.render_timer.start()

    def _auto_render(self):
        if self.thread:
            self._render_after_job = True
            return
        self.render_current(quiet=True)

    # ================================================================== menjalankan job
    def _start(self, job, label):
        if self.thread:
            return
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.log(f"— {label} —")
        self.thread = QThread()
        self.worker = Worker(job)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.log)
        self.worker.progress.connect(lambda a, b: (self.progress.setRange(0, b), self.progress.setValue(a)))
        self.worker.page_updated.connect(self._on_page_updated)
        self.worker.finished.connect(self._on_finished)
        self.thread.start()

    def _on_page_updated(self, i):
        self._update_page_item(i)
        if i == self.cur and getattr(self, "sel", None):
            self._update_fit_text()
        p = self.project.pages[i]
        if p.output_path and Path(p.output_path).exists():
            self.pages.item(i).setIcon(self._thumb(p.output_path))
        if i == self.cur:
            self._show_current()

    def _on_finished(self, err):
        self.thread.quit()
        self.thread.wait()
        self.thread = None
        self.worker = None
        self._set_busy(False)
        self._show_current()
        if err:
            self.log(f"✖ {err}")
            self.status_lbl.setText("Gagal — lihat tab LOG")
            QMessageBox.warning(self, APP_NAME, err)
        else:
            self.status_lbl.setText("Selesai ✔")
            if self.project.file:
                self.project.save()
        if self._render_after_job:
            self._render_after_job = False
            self._auto_render()

    def stop_job(self):
        if self.worker:
            self.worker.stop = True
            self.log("Menghentikan setelah halaman ini…")

    def translate_page(self):
        """Tombol Terjemahkan / F5. Bila halaman sudah punya kotak (hasil deteksi atau kotak manual),
        kotak itu dipakai: yang belum punya teks di-OCR, yang belum diterjemahkan diterjemahkan."""
        p = self.page()
        if p and p.blocks:
            self.run_stages(["detect", "ocr", "translate", "render"], keep_boxes=True)
        else:
            self.run_stages(["detect", "ocr", "translate", "render"])

    def run_stages(self, stages, keep_boxes=False):
        p = self.page()
        if not p:
            self.open_folder()
            return
        i, proj, st = self.cur, self.project, dict(self.settings)
        if any(x in stages for x in ("detect", "ocr", "translate")):
            self._snap(page=p)
        if "render" in stages:
            self.need_clean.discard(p.path)

        def job(w: Worker):
            from core import perf
            perf.apply(st)
            pipeline.process_page(p, proj, st, stages, log=w.log.emit, keep_boxes=keep_boxes)
            w.page_updated.emit(i)

        self._start(job, f"{', '.join(stages)} · {p.name}")

    def reset_font_memory(self):
        from core.pipeline import FONT_CAT_LABEL
        mem = self.project.font_memory
        if not mem:
            QMessageBox.information(self, APP_NAME, "Belum ada font yang diingat di proyek ini.")
            return
        lines = "\n".join(f"• {FONT_CAT_LABEL.get(k, k)}: {typeset.font_name(v) if v else 'font default'}"
                          for k, v in mem.items())
        from .alert import ask
        if ask(self, APP_NAME, "Lupakan font yang diingat?\n" + lines +
               "\n\nHalaman berikutnya akan dicocokkan ulang dengan teks aslinya.", yes="Lupakan", no="Batal"):
            self.project.font_memory = {}
            self.log("Memori font proyek dihapus.")

    def fix_ocr_all(self):
        """Perbaiki salah baca OCR (mis. 'GLEARIr' -> 'CLEAR!') di teks asli semua halaman, lalu
        (bila dipilih) terjemahkan ulang hanya balon yang berubah."""
        if self.thread or not self.project.pages:
            return
        from core import ocrfix
        if self.project.source_lang != "en":
            QMessageBox.information(self, APP_NAME, "Koreksi OCR otomatis saat ini untuk teks asli bahasa Inggris.\n"
                                    "Untuk bahasa lain, pakai mesin terjemah LLM: salah baca ikut dibetulkan "
                                    "saat menerjemahkan.")
            return
        changed = []
        self._snap()
        for i, pg in enumerate(self.project.pages):
            for b in pg.blocks:
                if b.kind == "title" or not (b.source or "").strip():
                    continue
                new = ocrfix.fix(b.source, "en")
                if new != b.source:
                    changed.append((i, pg, b, b.source, new))
        if not changed:
            QMessageBox.information(self, APP_NAME, "Tidak ada salah baca OCR yang perlu diperbaiki.")
            return
        sample = "\n".join(f"• {o}  →  {n}" for _, _, _, o, n in changed[:6])
        more = f"\n… dan {len(changed) - 6} lainnya" if len(changed) > 6 else ""
        ans = Alert(self, APP_NAME, f"{len(changed)} teks OCR diperbaiki", sample + more, kind="success",
                    buttons=[("Terapkan + terjemah ulang", "primary", "tr"), ("Terapkan saja", "neutral", "apply"),
                             ("Batal", "neutral", None)], escape_value=None).exec_value()
        if not ans:
            return
        for _, _, b, _, new in changed:
            b.source = new
        self._show_current()
        self.log(f"Koreksi OCR: {len(changed)} teks diperbaiki.")
        if ans != "tr":
            return
        pages = {}
        for i, pg, b, _, _ in changed:
            pages.setdefault(i, (pg, []))[1].append(b)
        proj, st = self.project, dict(self.settings)

        def job(w: Worker):
            items = sorted(pages.items())
            for n, (i, (pg, blocks)) in enumerate(items, 1):
                if w.stop:
                    break
                w.progress.emit(n - 1, len(items))
                try:
                    pipeline.step_translate(pg, proj, st, w.log.emit, only=blocks)
                    if pg.output_path or pg.status == "selesai":
                        pipeline.step_render(pg, proj, st, recalc_clean=False)
                except Exception as e:
                    w.log.emit(f"[{pg.name}] gagal: {e}")
                w.page_updated.emit(i)
            w.progress.emit(len(items), len(items))

        self._start(job, f"Terjemah ulang {len(changed)} balon")

    def detect_all(self):
        """Deteksi balon di semua halaman sekaligus (tanpa OCR / terjemah), supaya kotak bisa
        dicek & dirapikan dulu sebelum diterjemahkan."""
        if not self.project.pages:
            self.open_folder()
            return
        if self.thread:
            return
        pages = list(enumerate(self.project.pages))
        done = [x for x in pages if x[1].blocks]
        todo = pages
        if done:
            ans = Alert(self, APP_NAME, "Deteksi balon semua halaman",
                        f"{len(done)} dari {len(pages)} halaman sudah punya balon. Deteksi ulang akan "
                        "mengganti balon (beserta teks & terjemahannya) di halaman tersebut.",
                        kind="question",
                        buttons=[("Hanya yang belum", "primary", "new"), ("Deteksi ulang semua", "danger", "all"),
                                 ("Batal", "neutral", None)], escape_value=None).exec_value()
            if not ans:
                return
            if ans == "new":
                todo = [x for x in pages if not x[1].blocks]
                if not todo:
                    QMessageBox.information(self, APP_NAME, "Semua halaman sudah punya balon.")
                    return
        proj, st = self.project, dict(self.settings)
        for _, pg in todo:
            self._snap(page=pg)

        def job(w: Worker):
            total = 0
            for n, (i, p) in enumerate(todo, 1):
                if w.stop:
                    w.log.emit("Dihentikan.")
                    break
                w.progress.emit(n - 1, len(todo))
                try:
                    pipeline.process_page(p, proj, st, ["detect"], log=w.log.emit)
                    total += len(p.blocks)
                except ImportError:
                    raise
                except Exception as e:
                    w.log.emit(f"[{p.name}] gagal: {e}")
                w.page_updated.emit(i)
            w.progress.emit(len(todo), len(todo))
            w.log.emit(f"Deteksi selesai: {total} balon di {len(todo)} halaman.")

        self._start(job, f"Deteksi balon {len(todo)} halaman")

    def run_all(self):
        if not self.project.pages:
            self.open_folder()
            return
        todo = [(i, p) for i, p in enumerate(self.project.pages) if p.status != "selesai"]
        keep = True        # halaman yang sudah punya kotak (deteksi / manual) tidak dideteksi ulang
        if not todo:
            from .alert import ask
            if not ask(self, APP_NAME, "Semua halaman sudah selesai.\nProses ulang semua halaman dari awal?",
                       yes="Proses ulang", no="Batal"):
                return
            todo = list(enumerate(self.project.pages))
            keep = False
        proj, st = self.project, dict(self.settings)
        for _, pg in todo:
            self._snap(page=pg)
        cur_page = self.page()

        def job(w: Worker):
            import queue
            import threading
            import time
            from core import perf
            pipe = perf.pipelined(st)
            perf.apply(st, stages=2 if pipe else 1)
            low = perf.low_end(st)
            w.log.emit(f"Terjemahkan semua: {perf.describe(st)}"
                       + (" · 2 tahap bersamaan (baca halaman berikutnya sambil merender)" if pipe else ""))
            total = len(todo)
            done = [0]
            fatal = []

            def safe(fn, p, kp):
                try:
                    fn(p, proj, st, log=w.log.emit, keep_boxes=kp)
                    return True
                except ImportError as e:
                    fatal.append(e)
                except MemoryError:
                    # memori habis: bersihkan lalu ulangi dengan cara yang lebih ringan (tanpa AI hapus teks)
                    perf.release()
                    w.log.emit(f"[{p.name}] memori penuh — mencoba lagi dengan mode hemat…")
                    try:
                        fn(p, proj, dict(st, clean_method="opencv"), log=w.log.emit, keep_boxes=True)
                        return True
                    except Exception as e:
                        w.log.emit(f"[{p.name}] gagal: {e}")
                except Exception as e:
                    w.log.emit(f"[{p.name}] gagal: {e}")
                return False

            def finished_one(i, p):
                perf.release(p, keep_current=p is cur_page)
                done[0] += 1
                w.page_updated.emit(i)
                w.progress.emit(done[0], total)
                if proj.file and done[0] % 5 == 0:     # simpan otomatis: aman bila aplikasi tertutup paksa
                    try:
                        proj.save()
                        w.log.emit(f"Disimpan otomatis ({done[0]}/{total} halaman).")
                    except Exception:
                        pass
                if perf.free_ram_gb() < 0.6:
                    w.log.emit("Memori komputer hampir habis — jeda sebentar…")
                    perf.release()
                    time.sleep(1.5)

            w.progress.emit(0, total)
            if not pipe:
                for i, p in todo:
                    if w.stop or fatal:
                        break
                    kp = keep and bool(p.blocks)
                    if safe(pipeline.stage_read, p, kp):
                        safe(pipeline.stage_finish, p, kp)
                    finished_one(i, p)
                    if low:
                        time.sleep(0.15)               # beri napas untuk tampilan & sistem
            else:
                # tahap 2 (terjemah + render) berjalan di thread sendiri; antrean maks. 1 halaman
                # supaya memori tetap kecil
                q = queue.Queue(maxsize=1)

                def finisher():
                    while True:
                        item = q.get()
                        if item is None:
                            return
                        i, p, kp, ok = item
                        if ok and not w.stop and not fatal:
                            safe(pipeline.stage_finish, p, kp)
                        finished_one(i, p)

                th = threading.Thread(target=finisher, daemon=True)
                th.start()
                for i, p in todo:
                    if w.stop or fatal:
                        break
                    kp = keep and bool(p.blocks)
                    ok = safe(pipeline.stage_read, p, kp)
                    q.put((i, p, kp, ok))
                q.put(None)
                th.join()
            if w.stop:
                w.log.emit("Dihentikan.")
            if fatal:
                raise fatal[0]
            w.progress.emit(total, total)

        self._start(job, f"Terjemahkan {len(todo)} halaman")

    def render_current(self, quiet=False):
        p = self.page()
        if not p or self.thread:
            return
        recalc = p.path in self.need_clean
        self.need_clean.discard(p.path)
        i, proj, st = self.cur, self.project, dict(self.settings)

        def job(w: Worker):
            pipeline.step_render(p, proj, st, recalc_clean=recalc)
            w.page_updated.emit(i)

        self._start(job, f"Render {p.name}")
        if quiet:
            self.status_lbl.setText("Memperbarui hasil…")

    def _block_job(self, kind):
        p, b = self.page(), self.sel
        if not p or not b or self.thread:
            return
        ts = self._targets()
        if len(ts) > 1:
            return self._multi_job(kind, ts)
        proj, st, i = self.project, dict(self.settings), self.cur
        self._snap()
        rendered = bool(p.cleaned_path and Path(p.cleaned_path).exists())
        recalc = p.path in self.need_clean
        if rendered:
            self.need_clean.discard(p.path)

        def job(w: Worker):
            from core import detector, ocr, translator
            if kind in ("ocr", "ocr_only"):
                img = detector.load_image(p.path)
                b.source = ocr.ocr_block(img, b, st["ocr_engine"], proj.source_lang, st["gpu"])
                if not b.preset and not b.color2 and (b.color or "#000000").upper() == "#000000":
                    from core import textstyle
                    textstyle.apply(img, b)          # warna ikut teks aslinya
            if b.source.strip() and kind != "ocr_only":
                # "Terjemah ulang" = minta terjemahan baru (lewati cache); OCR ulang boleh pakai cache
                b.translation = pipeline.translate_texts([b.source], p, proj, st, use_cache=(kind == "ocr"))[0]
            w.log.emit(f"OCR: {b.source}" if kind == "ocr_only" else f"{b.source}  →  {b.translation}")
            if rendered:
                pipeline.step_render(p, proj, st, recalc_clean=recalc)
            w.page_updated.emit(i)

        self._start(job, {"ocr": "OCR + terjemah balon", "ocr_only": "OCR balon"}.get(kind, "Terjemah ulang balon"))

    def _multi_job(self, kind, blocks):
        """OCR ulang / terjemah ulang beberapa balon sekaligus (satu permintaan terjemahan)."""
        p, proj, st, i = self.page(), self.project, dict(self.settings), self.cur
        self._snap()
        rendered = bool(p.cleaned_path and Path(p.cleaned_path).exists())
        recalc = p.path in self.need_clean
        if rendered:
            self.need_clean.discard(p.path)

        def job(w: Worker):
            from core import detector, ocr
            if kind in ("ocr", "ocr_only"):
                img = detector.load_image(p.path)
                for b in blocks:
                    b.source = ocr.ocr_block(img, b, st["ocr_engine"], proj.source_lang, st["gpu"])
            todo = [b for b in blocks if b.source.strip()]
            if todo and kind != "ocr_only":
                res = pipeline.translate_texts([b.source for b in todo], p, proj, st, use_cache=(kind == "ocr"))
                for b, t in zip(todo, res):
                    b.translation = t
                    w.log.emit(f"{b.source}  →  {t}")
            if rendered:
                pipeline.step_render(p, proj, st, recalc_clean=recalc)
            w.page_updated.emit(i)

        lbl = {"ocr": "OCR + terjemah", "ocr_only": "OCR"}.get(kind, "Terjemah ulang")
        self._start(job, f"{lbl} {len(blocks)} balon")

    def _equal_font_size(self):
        b, ts = self.sel, self._targets()
        if not b or len(ts) < 2:
            return
        size = b.font_size or b.fit_size
        if not size:
            self.status_lbl.setText("Render halaman dulu supaya ukuran Auto balon aktif diketahui")
            return
        self._snap()
        for t in ts:
            t.font_size = int(size)
        self._load_props(b)
        self._schedule_render()
        self.status_lbl.setText(f"Ukuran teks {len(ts)} balon disamakan: {size}")

    def _equal_box_size(self):
        b, ts, p = self.sel, self._targets(), self.page()
        if not b or len(ts) < 2 or not p:
            return
        self._snap()
        for t in ts:
            if t is b:
                continue
            cx, cy = t.x + t.w / 2, t.y + t.h / 2
            t.w, t.h = int(b.w), int(b.h)
            t.x, t.y = int(round(cx - t.w / 2)), int(round(cy - t.h / 2))
        self.need_clean.add(p.path)
        for cv in (self.cv_src, self.cv_out):
            cv.reload_boxes()
        self._schedule_render()
        self.status_lbl.setText(f"Ukuran kotak {len(ts)} balon disamakan: {b.w}×{b.h}")

    # ================================================================== dialog & export
    def edit_settings(self):
        d = SettingsDialog(self.settings, self, project=self.project)
        if d.exec():
            if d.factory_reset:
                self.settings = pipeline.load_settings()       # pengaturan awal
            else:
                self.settings = d.result_settings()
            pipeline.save_settings(self.settings)
            for a in self.box_modes.actions():
                a.setChecked(a.data() == self.settings.get("box_mode", "box"))
            self._refresh_fonts()
            self.apply_shortcuts()
            self._update_preset_tips()
            self._schedule_render()
            self.log("Pengaturan disimpan.")

    def _refresh_fonts(self):
        """Isi ulang pilihan font di panel Tipografi (mis. setelah instal/hapus font)."""
        cur = self.p_font.currentData()
        self._loading = True
        self.p_font.clear()
        self.p_font.addItem("Font default", "")
        for f in typeset.list_fonts():
            self.p_font.addItem(typeset.font_name(f), f)
        self.p_font.setCurrentIndex(max(0, self.p_font.findData(cur)))
        self._loading = False

    def edit_glossary(self):
        d = GlossaryDialog(self.project.glossary, self)
        if d.exec():
            self.project.glossary = d.result_glossary()
            self.log(f"Glosarium: {len(self.project.glossary)} istilah.")

    # ================================================================== skill
    def _fill_style_menu(self):
        from core import skills
        m = self.m_style
        m.clear()
        cur = self.settings.get("tl_style", "alami")
        for k, (lab, _p) in skills.STYLES.items():
            a = m.addAction(lab, lambda k=k: self._set_style("tl_style", k))
            a.setCheckable(True)
            a.setChecked(k == cur)
        m.addSeparator()
        m.addAction("Honorifik (-san, senpai, oppa…)").setEnabled(False)
        hcur = self.settings.get("tl_honorific", "keep")
        for k, (lab, _p) in skills.HONORIFICS.items():
            a = m.addAction("   " + lab, lambda k=k: self._set_style("tl_honorific", k))
            a.setCheckable(True)
            a.setChecked(k == hcur)
        m.addSeparator()
        note = m.addAction("Berlaku untuk mesin LLM / AI" if self.settings.get("translate_engine") == "llm"
                           else "⚠ Hanya berlaku untuk mesin LLM / AI")
        note.setEnabled(False)

    def _set_style(self, key, val):
        from core import skills
        self.settings[key] = val
        pipeline.save_settings(self.settings)
        lab = (skills.STYLES if key == "tl_style" else skills.HONORIFICS)[val][0]
        self.log(f"Gaya bahasa: {lab} (berlaku untuk terjemahan berikutnya; "
                 "pakai Terjemah ulang untuk balon yang sudah ada)")

    def edit_story(self):
        from .skillsdlg import StoryDialog
        d = StoryDialog(self.project, self.settings, self)
        ok = d.exec()
        d.deleteLater()
        if ok:
            pipeline.save_settings(self.settings)
            self._refresh_state()
            from core import skills
            n = len(skills.story_of(self.project)["characters"])
            self.log(f"Memori cerita disimpan: {n} tokoh.")

    def _auto_story(self):
        """Proyek / chapter baru dibuka: pakai memori cerita seri yang sama bila ada."""
        from core import skills
        try:
            if skills.load_series(self.project):
                n = len(skills.story_of(self.project)["characters"])
                self.log(f"Memori cerita seri '{skills.series_key(self.project)}' dipakai ({n} tokoh).")
        except Exception:
            pass

    def proofread(self):
        if not self.project.pages:
            return
        if self.thread:
            return
        from .skillsdlg import ProofreadDialog
        d = ProofreadDialog(self.project, self.settings, self.cur, self)
        d.jump.connect(self._jump_block)
        d.exec()
        d.deleteLater()
        if d.changed:
            self._snap()
            self._render_pages(sorted(d.changed))

    def _jump_block(self, pi, bid):
        if pi != self.cur:
            self.pages.setCurrentRow(pi)
        p = self.page()
        b = next((x for x in p.blocks if x.id == bid), None) if p else None
        if b is not None:
            self._select(b)

    def _render_pages(self, idxs):
        proj, st = self.project, dict(self.settings)

        def job(w: Worker):
            for k, i in enumerate(idxs, 1):
                p = proj.pages[i]
                if p.cleaned_path or p.output_path:
                    pipeline.step_render(p, proj, st)
                    w.page_updated.emit(i)
                w.progress.emit(k, len(idxs))

        self._start(job, f"Render ulang {len(idxs)} halaman")

    def title_box(self):
        """Seret kotak di atas logo judul -> pembuat judul terbuka. Bila kotak judul sudah dipilih: langsung buka."""
        if not self.page() or self.thread:
            return
        if self.sel is not None and self.sel.kind == "title":
            self.edit_title(self.sel)
            return
        self._title_box = True
        if getattr(self, "tool", "select") != "select":
            self.set_tool("select")
        self.b_box.setChecked(True)
        self.cv_src.set_draw_mode(True)
        self.status_lbl.setText("Seret kotak di atas logo judul pada gambar ASLI…")
        self.log("Kotak judul: seret kotak di atas logo / tulisan judul pada gambar asli.")

    def edit_title(self, b=None):
        b = b or self.sel
        p = self.page()
        if not p or b is None or b not in p.blocks or self.thread:
            return
        from .titledlg import TitleDialog
        self._snap()
        if b.kind != "title":
            b.kind = "title"
        d = TitleDialog(self.project, p, b, self.settings, self)
        ok = d.exec()
        d.deleteLater()
        if ok:
            try:
                pipeline.save_settings(self.settings)
            except Exception:
                pass
            self._load_props(b)
            for cv in (self.cv_src, self.cv_out):
                cv.reload_boxes()
            self.need_clean.add(p.path)
            self.render_current()
            self.log("Judul: gambar buatan sendiri ditempel." if b.title_image else f"Judul: {b.translation}")

    def paste_title(self):
        """Ctrl+V saat kotak judul dipilih: tempel gambar judul dari clipboard."""
        b, p = self.sel, self.page()
        if not p or b is None or b.kind != "title" or self.thread:
            return
        cb = QApplication.clipboard()
        md = cb.mimeData()
        data = None
        if md is not None and md.hasImage() and not cb.image().isNull():
            from PySide6.QtCore import QBuffer, QIODevice
            buf = QBuffer()
            buf.open(QIODevice.WriteOnly)
            cb.image().save(buf, "PNG")
            data = bytes(buf.data())
        elif md is not None and md.hasUrls():
            data = next((u.toLocalFile() for u in md.urls() if u.isLocalFile()), None)
        if not data:
            self.log("Clipboard tidak berisi gambar judul.")
            return
        from core import titlelogo
        try:
            path = titlelogo.store_image(data)
        except Exception as e:
            self.log(f"Gambar judul tidak bisa dibaca: {e}")
            return
        self._snap()
        b.title_image = path
        self.need_clean.add(p.path)
        self.render_current()
        self.log("Judul buatan sendiri ditempel ke kotak judul (atur ukurannya lewat 'Pembuat judul').")

    def edit_credits(self):
        from .skillsdlg import CreditsDialog
        p = self.page()
        sample = p.output_path if p and p.output_path and Path(p.output_path).exists() else (p.path if p else None)
        d = CreditsDialog(self.settings, self.project.export_meta or {"series": self.project.series_title},
                          sample, self)
        ok = d.exec()
        d.deleteLater()
        if ok:
            pipeline.save_settings(self.settings)
            self.log("Kredit & watermark disimpan (centang di Export As untuk menambahkannya).")

    def export_as(self, fmt=None):
        """Dialog Export As: pratinjau + pilih halaman + PDF manga/manhwa/manhua, CBZ (ComicInfo), ZIP, PSD."""
        if not self.project.pages:
            QMessageBox.information(self, APP_NAME, "Belum ada halaman. Buka folder chapter dulu.")
            return
        if self.thread:
            return
        from .exportdlg import ExportDialog
        if fmt:
            self.settings.setdefault("export_opts", {})
            self.settings["export_opts"] = dict(self.settings.get("export_opts") or {}, fmt=fmt)
        d = ExportDialog(self.project, self.cur, self.settings, self)
        ok = d.exec()
        d.deleteLater()
        if not ok:
            return
        cfg = d.config()
        self.settings["export_opts"] = d.options()
        self.settings["export_dir"] = str(Path(cfg["out"]).parent)
        if cfg["meta"].get("translator"):
            self.settings["export_translator"] = cfg["meta"]["translator"]
        pipeline.save_settings(self.settings)
        if cfg["fmt"] == "cbz":
            self.project.export_meta = cfg["meta"]
            self._refresh_state()
        proj, st = self.project, dict(self.settings)

        def job(w: Worker):
            from core import exporter
            out = cfg.pop("out")
            r = exporter.export(proj, out, progress=w.progress.emit, stop=lambda: w.stop, settings=st,
                                log=w.log.emit, **cfg)
            jenis = {"manga": "manga", "manhwa": "manhwa", "manhua": "manhua"}[r["kind"]]
            if cfg["fmt"] == "pdf":
                w.log.emit(f"PDF {jenis}: {r['files']} gambar → {r['pages_out']} halaman PDF · {out}")
            elif cfg["fmt"] == "cbz":
                extra = " (paket Local Source Mihon)" if cfg["mihon_pack"] else " + ComicInfo.xml"
                w.log.emit(f"CBZ {jenis}{extra}: {r['files']} gambar · {out}")
            elif cfg["fmt"] == "psd":
                w.log.emit(f"PSD berlapis: {r['files']} halaman · {out}")
            else:
                w.log.emit(f"ZIP: {r['files']} gambar · {out}")

        self._start(job, "Export")

    def export_script(self):
        if not self.project.pages:
            return
        f, _ = QFileDialog.getSaveFileName(self, "Export skrip terjemahan", "skrip.txt", "Teks (*.txt)")
        if f:
            pipeline.export_text(self.project, f)
            self.log(f"Skrip diekspor: {f}")

    def open_output_folder(self):
        p = self.page() or (self.project.pages[0] if self.project.pages else None)
        if not p:
            return
        d = pipeline.output_dir(p, self.settings)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    def confirm_unsaved(self) -> bool:
        """Tanya simpan bila ada perubahan. True = boleh lanjut menutup, False = batal."""
        self._refresh_state()
        if not self._dirty:
            return True
        name = Path(self.project.file).name if self.project.file else "untitled.mtproj"
        choice = Alert(self, "Simpan proyek (.mtproj)", "Simpan perubahan sebelum menutup?",
                       f"Perubahan di “{name}” belum disimpan. Kalau tidak disimpan, perubahan terakhir hilang.",
                       kind="save",
                       buttons=[("Simpan .mtproj", "primary", "save"), ("Jangan simpan", "danger", "discard"),
                                ("Batal", "neutral", "cancel")],
                       escape_value="cancel").exec_value()
        if choice == "save":
            return self.save_project()       # dialog simpan dibatalkan -> tetap di aplikasi
        return choice == "discard"

    def closeEvent(self, e):
        if getattr(self, "_closing_confirmed", False) or self.confirm_unsaved():
            e.accept()
        else:
            e.ignore()

STYLE = """
* { font-family: 'Inter', 'Segoe UI', 'Noto Sans', sans-serif; font-size: 9.5pt; color: #d5dbea; }
QMainWindow, QWidget { background: #131722; }
QToolBar { background: #191e2a; border: none; border-bottom: 1px solid #252b3b; padding: 5px 8px; spacing: 4px; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 5px; }
QToolButton:hover { background: #2a3142; border-color: #343c50; }
QToolButton:checked { background: #343c50; border-color: #7c6cff; }
QToolButton::menu-indicator { image: none; }
QToolButton:disabled { background: transparent; border-color: transparent; color: #3e4558; }
QLineEdit#numField:disabled { color: #3e4558; }
QToolButton#primary { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f86ff, stop:1 #8a63f0); color: white; font-family: 'Plus Jakarta Sans', 'Inter', 'Segoe UI', sans-serif; font-weight: 700; padding: 6px 12px; border: none; }
QToolButton#primary:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6596ff, stop:1 #9b78f5); }
QToolButton#primary:disabled { background: #38365f; color: #a7a3cc; }
QToolButton#primary::menu-button { border-left: 1px solid #a598ff; width: 18px; }
QToolButton#splitBtn { padding-right: 17px; }
QToolButton#splitBtn::menu-button { width: 14px; border: none; border-left: 1px solid #2e3547;
  border-top-right-radius: 6px; border-bottom-right-radius: 6px; }
QToolButton#splitBtn::menu-button:hover { background: #343c50; }
QFrame#sep { color: #2e3547; max-width: 1px; margin: 4px 6px; }
QLabel#pageLbl { font-family: 'Plus Jakarta Sans', 'Inter', 'Segoe UI', sans-serif; font-weight: 700; }
QLabel#dim { color: #8089a3; }
QComboBox, QSpinBox, QPlainTextEdit, QLineEdit, QTextEdit, QDoubleSpinBox {
  background: #202636; border: 1px solid #313849; border-radius: 6px; padding: 4px 6px; }
QComboBox:hover, QSpinBox:hover { border-color: #455069; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox { combobox-popup: 0; }   /* daftar pilihan bisa digulir (tidak memanjang setinggi layar) */
QComboBox QAbstractItemView QScrollBar:vertical { width: 10px; }
QComboBox QAbstractItemView { background: #202636; selection-background-color: #7c6cff; }
QPlainTextEdit:focus, QLineEdit:focus { border-color: #7c6cff; }
QWidget#panel { background: #171b27; }
QWidget#pagesHdr { background: #171b27; border-bottom: 1px solid #252b3b; }
QWidget#pagesHdr QLabel#panelHeader { border-bottom: none; }
QToolButton#hdrBtn { padding: 3px; border-radius: 5px; }
QLabel#panelHeader { font-family: 'Plus Jakarta Sans', 'Inter', 'Segoe UI', sans-serif; background: #171b27; color: #9ca4bb; font-weight: 700; font-size: 7.5pt;
  padding: 9px 10px; border-bottom: 1px solid #252b3b; }
QListWidget { background: #171b27; border: none; outline: 0; }
QListWidget::item { padding: 4px; border-radius: 6px; border-left: 3px solid transparent; }
QListWidget::item:hover { background: #222838; }
QListWidget::item:selected { background: #2a3142; border-left: 3px solid #7c6cff; color: white; }
QWidget#viewHeaderBar { background: #171b27; border-bottom: 1px solid #252b3b; }
QLabel#viewHeader { font-family: 'Plus Jakarta Sans', 'Inter', 'Segoe UI', sans-serif; color: #9ca4bb; font-weight: 700; font-size: 8.5pt; padding: 8px; background: transparent; }
QWidget#viewHeaderBar QComboBox { padding: 1px 6px; margin-right: 6px; }
QTabWidget#rightTabs::pane { border: none; background: #171b27; }
QTabBar::tab { font-family: 'Plus Jakarta Sans', 'Inter', 'Segoe UI', sans-serif; background: #171b27; color: #8b93ab; padding: 7px 9px; font-weight: 700; font-size: 7.5pt;
  border: none; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: white; border-bottom: 2px solid #7c6cff; }
QTabBar::tab:hover { color: #d5dbea; }
QToolButton#sectionHeader { font-family: 'Plus Jakarta Sans', 'Inter', 'Segoe UI', sans-serif; font-weight: 700; }
QLabel#cardTitle { font-family: 'Plus Jakarta Sans', 'Inter', 'Segoe UI', sans-serif; font-weight: 700; font-size: 10pt; background: transparent; }
QFrame#card { background: #1c2130; border: 1px solid #2a3142; border-radius: 8px; }
QFrame#card QLabel { background: transparent; }
QToolButton#styleToggle { background: #202636; border: 1px solid #313849; }
QToolButton#styleToggle:checked { background: #7c6cff; border-color: #7c6cff; color: white; }
QKeySequenceEdit QLineEdit { background: #202636; }
QWidget#field { background: #202636; border: 1px solid #313849; border-radius: 5px; min-height: 24px; }
QWidget#propsPanel, QWidget#propsPanel QLabel, QWidget#propsPanel QComboBox, QWidget#propsPanel QPushButton,
QWidget#propsPanel QToolButton, QWidget#propsPanel QSpinBox, QWidget#propsPanel QDoubleSpinBox,
QWidget#propsPanel QPlainTextEdit, QWidget#propsPanel QCheckBox { font-size: 8pt; }
QWidget#propsPanel QComboBox { padding: 2px 6px; min-height: 22px; }
QWidget#propsPanel QPushButton { padding: 4px 6px; }
QLabel#fieldIcon { color: #8b93ab; font-weight: 600; background: transparent; min-width: 16px; }
QLineEdit#numField { background: transparent; border: none; padding: 0 2px; margin: 0; color: #e3e8f3;
  font-size: 8.5pt; selection-background-color: #7c6cff; }
QLineEdit#numField:focus { background: #181d29; border-radius: 3px; }
QSpinBox#bare, QDoubleSpinBox#bare { background: transparent; border: none; padding: 0 2px; margin: 0;
  color: #e3e8f3; min-height: 20px; selection-background-color: #7c6cff; }
QToolButton#mini { background: #202636; border: 1px solid #313849; border-radius: 6px; padding: 0; }
QToolButton#mini:hover { background: #2a3142; }
QToolButton#mini:checked { background: #7c6cff; border-color: #7c6cff; color: white; }
QPushButton#swatch { min-height: 24px; padding: 2px 6px; font-size: 8.5pt; }
QToolButton#presetBtn { background: #202636; border: 1px solid #313849; font-weight: 600; padding: 0; }
QToolButton#presetBtn:checked { background: #7c6cff; border-color: #7c6cff; color: white; }
QToolButton#sectionHeader { background: #202636; color: #e3e8f3; font-weight: 600; font-size: 7.5pt;
  text-align: left; padding: 6px 4px; border-radius: 5px; border: none; }
QWidget#sectionBody { background: transparent; }
QLabel#fieldLabel { color: #8b93ab; font-size: 8.5pt; }
QPushButton { background: #2a3142; border: 1px solid #343c50; border-radius: 6px; padding: 6px 10px; }
QPushButton:hover { background: #343c50; }
QPushButton#danger { color: #ff8a95; }
QTableWidget { background: #171b27; border: none; gridline-color: #252b3b; }
QTableWidget::item:selected { background: #2f2d55; color: white; }
QHeaderView::section { background: #1c2130; color: #9ca4bb; border: none; padding: 6px; font-weight: 600; }
QScrollArea { background: #171b27; }
QScrollBar:vertical, QScrollBar:horizontal { background: transparent; width: 10px; height: 10px; }
QScrollBar::handle { background: #343c50; border-radius: 4px; min-height: 30px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QStatusBar { background: #191e2a; border-top: 1px solid #252b3b; }
QStatusBar QLabel { padding: 0 8px; }
QProgressBar { background: #2a3142; border: none; border-radius: 4px; }
QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f86ff, stop:1 #8a63f0); border-radius: 4px; }
QSplitter::handle { background: #252b3b; width: 1px; }
QSplitter#viewsSplit::handle { background: #252b3b; }
QSplitter#viewsSplit::handle:hover { background: #7c6cff; }
QMenu { background: #202636; border: 1px solid #343c50; padding: 4px; }
QMenu::item { padding: 6px 18px 6px 10px; border-radius: 4px; }
QMenu::item:selected { background: #7c6cff; color: white; }
QMenu::separator { height: 1px; background: #343c50; margin: 4px 6px; }
QCheckBox { spacing: 8px; background: transparent; }
QToolTip { background: #202636; color: #e3e8f3; border: 1px solid #343c50; padding: 4px; }
"""


def _rollback_after_crash() -> bool:
    """Update terakhir membuat jendela gagal dibuka: pulihkan app.old -> app lalu jalankan ulang.
    (Peluncur hanya memulihkan otomatis bila kode gagal dimuat; ini menangani error saat jendela dibuat.)"""
    import os
    import sys
    import traceback
    from core import paths
    if not paths.is_frozen() or os.environ.get("REXXA_ROLLED_BACK"):
        return False
    code = Path(paths.code_dir())
    old, broken = code.with_name(code.name + ".old"), code.with_name(code.name + ".broken")
    if not old.is_dir():
        return False
    try:
        (paths.data_dir() / "crash.txt").write_text(traceback.format_exc(), encoding="utf-8")
        import shutil
        shutil.rmtree(broken, ignore_errors=True)
        os.replace(code, broken)
        os.replace(old, code)
    except OSError:
        return False
    import subprocess
    env = dict(os.environ, REXXA_ROLLED_BACK="1")
    subprocess.Popen([sys.executable] + sys.argv[1:], env=env, close_fds=True)
    return True


def run():
    import sys
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    from core.paths import code_dir
    chev = code_dir() / "assets" / "chevron_down.svg"
    extra = ""
    if chev.exists():
        extra = ("QToolButton#splitBtn::menu-arrow { image: url(%s); width: 9px; height: 9px; }"
                 % chev.as_posix())
    from . import uifonts
    uifonts.load()
    app.setStyleSheet(STYLE + extra)
    ic = code_dir() / "assets" / "icon.png"
    if ic.exists():
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(str(ic)))
    try:
        w = MainWindow()
    except Exception:
        if _rollback_after_crash():
            return
        raise
    w.show()
    if len(sys.argv) > 1:
        w._load_paths(sys.argv[1:])
    sys.exit(app.exec())
