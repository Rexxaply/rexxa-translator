"""Dialog "Export As" ala dialog print: pratinjau di kiri, pilihan di kanan.

Halaman : saat ini / semua / rentang (mis. 1-5, 8)
Format  : PDF · CBZ + ComicInfo.xml (Mihon, Komga, Kavita…) · ZIP gambar
Jenis   : Otomatis · Manga (1 gambar = 1 halaman, kanan→kiri) · Manhwa / Manhua (strip disambung)
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QImageReader, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem,
                               QPushButton, QRadioButton, QScrollArea, QSpinBox, QStackedWidget, QTextEdit,
                               QToolButton, QVBoxLayout, QWidget)

from core import exporter

from .icons import icon

FORMATS = [("PDF", "pdf"), ("CBZ + ComicInfo.xml (Mihon)", "cbz"), ("ZIP gambar saja", "zip"),
           ("PSD berlapis (Photoshop)", "psd")]
KINDS = [("Otomatis (deteksi)", "auto"), ("Manga — per halaman", "manga"),
         ("Manhwa — strip disambung", "manhwa"), ("Manhua — strip disambung", "manhua")]
IMG = [("Asli (tanpa kompres ulang)", "asli"), ("JPG (lebih kecil)", "jpg"), ("WebP (paling kecil)", "webp")]

_PIX: dict = {}


def _load(path: str, w: int = 0, h: int = 0) -> QPixmap:
    """Gambar diperkecil langsung saat dibaca (hemat memori); cache per ukuran."""
    try:
        st = os.stat(path)
        k = (path, st.st_mtime_ns, w, h)
    except OSError:
        return QPixmap()
    pm = _PIX.get(k)
    if pm is not None:
        return pm
    r = QImageReader(path)
    r.setAutoTransform(True)
    s = r.size()
    if s.isValid() and s.width() > 0 and s.height() > 0:
        sc = min(w / s.width() if w else 9e9, h / s.height() if h else 9e9, 1.0)
        if sc < 1.0:
            r.setScaledSize(QSize(max(1, int(s.width() * sc)), max(1, int(s.height() * sc))))
    pm = QPixmap.fromImage(r.read())
    if len(_PIX) > 400:
        _PIX.clear()
    _PIX[k] = pm
    return pm


def _card(title: str):
    f = QFrame()
    f.setObjectName("card")
    v = QVBoxLayout(f)
    v.setContentsMargins(10, 8, 10, 10)
    v.setSpacing(6)
    t = QLabel(title)
    t.setObjectName("cardTitle")
    v.addWidget(t)
    return f, v


class ExportDialog(QDialog):
    def __init__(self, project, cur: int, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export As")
        self.project, self.cur, self.settings = project, max(0, cur), settings
        self.out_path = ""
        self.credits_changed = False
        self.files: list[tuple[int, str]] = []
        self.view: list[tuple[int, str]] = []
        self.view_i = 0
        self._strip_labels: list[QLabel] = []
        self._load_q: list = []
        opts = dict(settings.get("export_opts") or {})
        meta = dict(project.export_meta or {})
        self.resize(1080, 720)

        self.setStyleSheet(
            "QFrame#card QLabel, QFrame#card QRadioButton, QFrame#card QCheckBox { background: transparent; }"
            "QRadioButton::indicator, QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #56607a;"
            " background: #202636; }"
            "QRadioButton::indicator { border-radius: 8px; }"
            "QCheckBox::indicator { border-radius: 3px; }"
            "QRadioButton::indicator:checked { background: qradialgradient(cx:.5, cy:.5, radius:.5, fx:.5, fy:.5,"
            " stop:0 #7c6cff, stop:.45 #7c6cff, stop:.55 #202636, stop:1 #202636); border-color: #7c6cff; }"
            "QCheckBox::indicator:checked { background: #7c6cff; border-color: #7c6cff; }"
            "QRadioButton::indicator:hover, QCheckBox::indicator:hover { border-color: #a598ff; }")
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # ---------------- kiri: pratinjau
        left = QVBoxLayout()
        bar = QHBoxLayout()
        self.prev_lbl = QLabel("Pratinjau")
        self.prev_lbl.setObjectName("dim")
        self.b_prev = QToolButton()
        self.b_prev.setIcon(icon("prev"))
        self.b_prev.clicked.connect(lambda: self._go(self.view_i - 1))
        self.b_next = QToolButton()
        self.b_next.setIcon(icon("next"))
        self.b_next.clicked.connect(lambda: self._go(self.view_i + 1))
        self.pos_lbl = QLabel("")
        self.pos_lbl.setObjectName("pageLbl")
        bar.addWidget(self.prev_lbl)
        bar.addStretch(1)
        bar.addWidget(self.b_prev)
        bar.addWidget(self.pos_lbl)
        bar.addWidget(self.b_next)
        left.addLayout(bar)

        self.stack = QStackedWidget()
        # mode halaman (manga): satu halaman pas di layar
        self.single = QScrollArea()
        self.single.setWidgetResizable(True)
        self.single.setAlignment(Qt.AlignCenter)
        self.single_lbl = QLabel()
        self.single_lbl.setAlignment(Qt.AlignCenter)
        self.single.setWidget(self.single_lbl)
        self.single.setStyleSheet("QScrollArea{background:#0c0f16;border:1px solid #252b3b;border-radius:6px}"
                                  "QLabel{background:#0c0f16}")
        # mode strip (manhwa/manhua): disambung, gulir vertikal
        self.strip = QScrollArea()
        self.strip.setWidgetResizable(True)
        self.strip.setStyleSheet(self.single.styleSheet())
        self.strip_w = QWidget()
        self.strip_v = QVBoxLayout(self.strip_w)
        self.strip_v.setContentsMargins(0, 0, 0, 0)
        self.strip_v.setSpacing(0)
        self.strip_v.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.strip.setWidget(self.strip_w)
        self.strip.verticalScrollBar().valueChanged.connect(self._strip_scrolled)
        self.stack.addWidget(self.single)
        self.stack.addWidget(self.strip)
        left.addWidget(self.stack, 1)

        self.thumbs = QListWidget()
        self.thumbs.setViewMode(QListView.IconMode)
        self.thumbs.setFlow(QListView.LeftToRight)
        self.thumbs.setWrapping(False)
        self.thumbs.setMovement(QListView.Static)
        self.thumbs.setIconSize(QSize(64, 92))
        self.thumbs.setFixedHeight(128)
        self.thumbs.setSpacing(4)
        self.thumbs.currentRowChanged.connect(self._thumb_clicked)
        left.addWidget(self.thumbs)
        root.addLayout(left, 1)

        # ---------------- kanan: pilihan
        panel = QWidget()
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(0, 0, 4, 0)
        pv.setSpacing(8)

        c, v = _card("Halaman")
        n = len(project.pages)
        self.r_cur = QRadioButton(f"Halaman saat ini  ({self.cur + 1})")
        self.r_all = QRadioButton(f"Semua halaman  ({n})")
        self.r_rng = QRadioButton("Rentang:")
        self.rng = QLineEdit(opts.get("range", ""))
        self.rng.setPlaceholderText("mis. 1-5, 8, 10-12")
        self.scope = QButtonGroup(self)
        for i, r in enumerate((self.r_cur, self.r_all, self.r_rng)):
            self.scope.addButton(r, i)
        {"cur": self.r_cur, "range": self.r_rng}.get(opts.get("scope"), self.r_all).setChecked(True)
        v.addWidget(self.r_cur)
        v.addWidget(self.r_all)
        h = QHBoxLayout()
        h.addWidget(self.r_rng)
        h.addWidget(self.rng, 1)
        v.addLayout(h)
        self.use_orig = QCheckBox("Sertakan yang belum diterjemahkan")
        self.use_orig.setToolTip("Halaman yang belum diterjemahkan ikut diekspor memakai gambar aslinya.\n"
                                 "Bila tidak dicentang, halaman itu dilewati.")
        self.use_orig.setChecked(bool(opts.get("use_original", False)))
        v.addWidget(self.use_orig)
        self.sel_info = QLabel("")
        self.sel_info.setObjectName("dim")
        self.sel_info.setWordWrap(True)
        v.addWidget(self.sel_info)
        pv.addWidget(c)

        c, v = _card("Format")
        f = QFormLayout()
        f.setContentsMargins(0, 0, 0, 0)
        self.fmt = self._combo(FORMATS, opts.get("fmt", "pdf"))
        self.kind = self._combo(KINDS, opts.get("kind", "auto"))
        self.img = self._combo(IMG, opts.get("img_fmt", "asli"))
        self.q = QSpinBox()
        self.q.setRange(40, 100)
        self.q.setSuffix(" %")
        self.q.setValue(int(opts.get("quality", 90)))
        f.addRow("Simpan sebagai", self.fmt)
        f.addRow("Jenis", self.kind)
        self.img_row = QLabel("Gambar")
        f.addRow(self.img_row, self.img)
        f.addRow("Kualitas", self.q)
        v.addLayout(f)
        self.fmt_info = QLabel("")
        self.fmt_info.setObjectName("dim")
        self.fmt_info.setWordWrap(True)
        v.addWidget(self.fmt_info)
        pv.addWidget(c)

        self.meta_card, v = _card("Info seri · ComicInfo.xml")
        f = QFormLayout()
        f.setContentsMargins(0, 0, 0, 0)
        self.m_series = QLineEdit(meta.get("series") or project.series_title or
                                  (Path(project.pages[0].path).parent.parent.name if project.pages else ""))
        self.m_ch = QLineEdit(meta.get("chapter") or exporter.guess_chapter(project))
        self.m_ch.setPlaceholderText("mis. 12 atau 12.5")
        self.m_title = QLineEdit(meta.get("chapter_title", ""))
        self.m_author = QLineEdit(meta.get("author", ""))
        self.m_tl = QLineEdit(meta.get("translator") or settings.get("export_translator", ""))
        self.m_genre = QLineEdit(meta.get("genre", ""))
        self.m_genre.setPlaceholderText("Action, Romance, …")
        self.m_status = QComboBox()
        self.m_status.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.m_status.addItems(list(exporter.STATUS))
        self.m_status.setCurrentText(meta.get("status", "Tidak diketahui"))
        self.m_sum = QTextEdit(meta.get("summary", ""))
        self.m_sum.setFixedHeight(60)
        self.m_sum.setPlaceholderText("Ringkasan cerita (opsional)")
        for lab, w in (("Judul seri", self.m_series), ("Chapter", self.m_ch), ("Judul chapter", self.m_title),
                       ("Penulis", self.m_author), ("Penerjemah", self.m_tl), ("Genre", self.m_genre),
                       ("Status", self.m_status), ("Ringkasan", self.m_sum)):
            f.addRow(lab, w)
        v.addLayout(f)
        self.mihon = QCheckBox("Paket Local Source Mihon")
        self.mihon.setChecked(bool(opts.get("mihon_pack", False)))
        self.mihon.setToolTip("Hasil .zip berisi folder seri. Ekstrak ke folder Mihon/local/ di HP,\n"
                              "lalu buka Browse → Local source.")
        v.addWidget(self.mihon)
        pv.addWidget(self.meta_card)

        self.extra_card, v = _card("Tambahan")
        self.c_credit = QCheckBox("Halaman kredit tim")
        self.c_credit.setChecked(bool(opts.get("credit_page", False)))
        self.c_wm = QCheckBox("Watermark di setiap halaman")
        self.c_wm.setChecked(bool(opts.get("watermark", False)))
        b_cr = QPushButton("Atur kredit && watermark…")
        b_cr.clicked.connect(self._edit_credits)
        v.addWidget(self.c_credit)
        v.addWidget(self.c_wm)
        v.addWidget(b_cr)
        pv.addWidget(self.extra_card)
        pv.addStretch(1)

        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setWidget(panel)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setFixedWidth(392)
        panel.setFixedWidth(376)
        right = QVBoxLayout()
        right.addWidget(sc, 1)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        right.addWidget(self.summary)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Batal")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("Export…")
        self.ok.setDefault(True)
        self.ok.setStyleSheet("QPushButton{background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f86ff, stop:1 #8a63f0);color:white;font-weight:600;border:none;"
                              "border-radius:6px;padding:7px 18px}QPushButton:hover{background:qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6596ff, stop:1 #9b78f5)}"
                              "QPushButton:disabled{background:#38365f;color:#a7a3cc}")
        self.ok.clicked.connect(self._do_export)
        btns.addWidget(cancel)
        btns.addWidget(self.ok)
        right.addLayout(btns)
        root.addLayout(right)

        # ---------------- sinyal
        self._timer = QTimer(self, singleShot=True, interval=250, timeout=self._refresh)
        self.scope.idClicked.connect(lambda _i: self._refresh())
        self.rng.textEdited.connect(lambda _t: (self.r_rng.setChecked(True), self._timer.start()))
        self.use_orig.toggled.connect(lambda _b: self._refresh())
        self.fmt.currentIndexChanged.connect(lambda _i: self._update_ui())
        self.kind.currentIndexChanged.connect(lambda _i: self._refresh())
        self.img.currentIndexChanged.connect(lambda _i: self._update_ui())
        self.mihon.toggled.connect(lambda _b: self._update_ui())
        self.c_credit.toggled.connect(lambda _b: (self._update_ui(), self._build_preview()))
        self.c_wm.toggled.connect(lambda _b: (self._update_ui(), self._build_preview()))
        self._loader = QTimer(self, interval=0, timeout=self._load_step)
        self._resize_t = QTimer(self, singleShot=True, interval=150, timeout=self._relayout)
        self._update_ui()
        self._refresh()

    # ---------------------------------------------------------------- util
    @staticmethod
    def _combo(items, value):
        c = QComboBox()
        c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        c.setMinimumContentsLength(8)
        for lab, v in items:
            c.addItem(lab, v)
        c.setCurrentIndex(max(0, c.findData(value)))
        return c

    def _indices(self) -> list[int]:
        n = len(self.project.pages)
        if self.r_cur.isChecked():
            return [min(self.cur, n - 1)] if n else []
        if self.r_rng.isChecked():
            return exporter.parse_range(self.rng.text(), n)
        return list(range(n))

    def _kind(self) -> str:
        k = self.kind.currentData()
        if k == "auto":
            k = exporter.detect_kind([p for _, p in self.files]) if self.files else "manga"
        return k

    # ---------------------------------------------------------------- tampilan
    def _update_ui(self):
        fmt = self.fmt.currentData()
        psd = fmt == "psd"
        self.extra_card.setVisible(not psd)
        self.meta_card.setVisible(fmt == "cbz" or (self.c_credit.isChecked() and not psd))
        self.mihon.setVisible(fmt == "cbz")
        self.img.setEnabled(fmt not in ("pdf", "psd"))
        self.kind.setEnabled(not psd)
        self.use_orig.setEnabled(not psd)
        self.q.setEnabled(fmt == "pdf" or (not psd and self.img.currentData() != "asli"))
        info = {
            "pdf": "Satu file .pdf. Manga = 1 gambar per halaman; manhwa/manhua = semua halaman disambung "
                   "lalu dipotong di celah antar panel supaya panel tidak terbelah.",
            "cbz": "Arsip komik standar: gambar 001, 002, … + ComicInfo.xml (judul, chapter, arah baca). "
                   "Bisa dibaca Mihon (Local source), Komga, Kavita, CDisplayEx, dll.",
            "zip": "Hanya gambar bernomor urut, tanpa info tambahan.",
            "psd": "Satu .psd per halaman (lebih dari 1 halaman → dibungkus .zip). Lapisan: Raw (asli, "
                   "disembunyikan) · Bersih (tanpa teks) · satu lapisan per balon teks (bisa digeser / "
                   "diwarnai ulang, tapi berupa gambar, bukan teks yang bisa diketik ulang). "
                   "Bisa dibuka Photoshop, Photopea, GIMP, Krita.",
        }[fmt]
        if fmt == "cbz" and self.mihon.isChecked():
            info += "\nPaket Mihon: ekstrak .zip ke Mihon/local/ di HP → Browse → Local source."
        self.fmt_info.setText(info)
        self._update_summary()

    def _refresh(self):
        """Hitung ulang halaman terpilih lalu muat pratinjau."""
        try:
            idx = self._indices()
            err = ""
        except ValueError as e:
            idx, err = [], str(e)
        use = self.use_orig.isChecked()
        self.files = [(i, f) for i in idx if (f := exporter.page_file(self.project.pages[i], use))]
        missing = sum(1 for i in idx if not exporter.page_file(self.project.pages[i], False))
        if err:
            self.sel_info.setText(f"<span style='color:#ff7a85'>{err}</span>")
        else:
            t = f"{len(idx)} halaman dipilih"
            if missing:
                t += (f" · {missing} belum diterjemahkan " +
                      ("(pakai gambar asli)" if use else "(dilewati)"))
            self.sel_info.setText(t)
        self._build_preview()
        self._update_summary()

    def _update_summary(self):
        n = len(self.files)
        self.ok.setEnabled(n > 0)
        if not n:
            self.summary.setText("<span style='color:#ff7a85'>Tidak ada halaman yang bisa diekspor.</span>")
            return
        fmt, kind = self.fmt.currentData(), self._kind()
        nama = {"manga": "Manga", "manhwa": "Manhwa", "manhua": "Manhua"}[kind]
        if fmt == "pdf":
            out = exporter.estimate_pdf_pages([p for _, p in self.files], kind)
            t = f"<b>{n} gambar → ±{out} halaman PDF</b> · {nama}"
        elif fmt == "cbz":
            t = f"<b>{n} gambar → 1 file {'.zip (paket Mihon)' if self.mihon.isChecked() else '.cbz'}</b> · {nama}"
        elif fmt == "psd":
            t = f"<b>{n} halaman → {'1 file .psd' if n == 1 else f'{n} file .psd (dalam .zip)'}</b>"
        else:
            t = f"<b>{n} gambar → 1 file .zip</b>"
        if fmt != "psd":
            plus = [x for x, on in (("halaman kredit", self.c_credit.isChecked()),
                                    ("watermark", self.c_wm.isChecked())) if on]
            if plus:
                t += " · + " + " & ".join(plus)
        self.summary.setText(t)

    # ---------------------------------------------------------------- kredit & watermark di pratinjau
    def _extras_on(self):
        fmt = self.fmt.currentData()
        return fmt != "psd" and self.c_credit.isChecked(), fmt != "psd" and self.c_wm.isChecked()

    def _preview_files(self):
        view = list(self.files)
        page_on, _wm = self._extras_on()
        if page_on and view:
            from core import skills
            import hashlib
            import json
            import tempfile
            cfg = skills.credits_cfg(self.settings)
            kind = self._kind()
            from PIL import Image
            with Image.open(view[0][1]) as im:
                W, H = im.size
            if kind != "manga" or H > W * 2.2:
                H = int(W * 1.4)
            key = hashlib.md5(json.dumps([cfg, self.meta(), W, H], sort_keys=True, default=str).encode()).hexdigest()
            f = Path(tempfile.gettempdir()) / f"rexxa_kredit_{key[:12]}.png"
            if not f.exists():
                skills.credit_page(cfg, (W, H), self.meta()).save(f)
            pos = cfg.get("position", "end")
            if pos in ("start", "both"):
                view = [(-1, str(f))] + view
            if pos in ("end", "both"):
                view = view + [(-1, str(f))]
        return view

    def _pm(self, k, w, h):
        i, f = self.view[k]
        _page, wm = self._extras_on()
        if not wm or i < 0 or (w and w < 200):          # thumbnail kecil: watermark tidak terbaca
            return _load(f, w, h)
        from core import skills
        cfg = skills.credits_cfg(self.settings)
        key = ("wm", f, w, h, repr(sorted((a, str(b)) for a, b in cfg.items() if a.startswith("wm") or a == "team")))
        pm = _PIX.get(key)
        if pm is None:
            from PIL import Image
            try:
                with Image.open(f) as im:
                    im = im.convert("RGB")
                    sc = min(w / im.width if w else 9e9, h / im.height if h else 9e9, 1.0)
                    if sc < 1.0:
                        im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))))
                    im = skills.watermark(im, cfg)
                data = im.tobytes("raw", "RGB")
                from PySide6.QtGui import QImage
                pm = QPixmap.fromImage(QImage(data, im.width, im.height, im.width * 3, QImage.Format_RGB888).copy())
            except Exception:
                pm = _load(f, w, h)
            _PIX[key] = pm
        return pm

    def _build_preview(self):
        self._loader.stop()
        self.view = self._preview_files()
        kind = self._kind()
        strip = kind in ("manhwa", "manhua")
        self.stack.setCurrentIndex(1 if strip else 0)
        self.thumbs.blockSignals(True)
        self.thumbs.clear()
        for k, (i, f) in enumerate(self.view):
            it = QListWidgetItem(str(i + 1) if i >= 0 else "Kredit")
            it.setTextAlignment(Qt.AlignHCenter)
            it.setSizeHint(QSize(76, 116))
            self.thumbs.addItem(it)
        self.thumbs.blockSignals(False)
        # strip: label kosong dulu (tinggi perkiraan), diisi bertahap supaya dialog tetap responsif
        while self.strip_v.count():
            w = self.strip_v.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._strip_labels = []
        if strip:
            W = self._strip_width()
            for _i, f in self.view:
                lb = QLabel()
                lb.setAlignment(Qt.AlignCenter)
                r = QImageReader(f)
                s = r.size()
                hh = int(s.height() * W / s.width()) if s.isValid() and s.width() else W
                lb.setFixedSize(W, max(1, hh))
                self.strip_v.addWidget(lb)
                self._strip_labels.append(lb)
        self._load_q = [("t", k) for k in range(len(self.view))]
        if strip:
            self._load_q = [("s", k) for k in range(len(self.view))] + self._load_q
        self.view_i = 0 if not (0 <= self.view_i < len(self.view)) else self.view_i
        if not strip and self.view:
            # mulai dari halaman saat ini bila ikut terpilih
            for k, (i, _f) in enumerate(self.view):
                if i == self.cur:
                    self.view_i = k
                    break
        self._go(self.view_i)
        self._loader.start()

    def _strip_width(self) -> int:
        return max(200, min(560, self.strip.viewport().width() - 24))

    def _load_step(self):
        if not self._load_q:
            self._loader.stop()
            return
        what, k = self._load_q.pop(0)
        if k >= len(self.view):
            return
        f = self.view[k][1]
        if what == "t":
            it = self.thumbs.item(k)
            if it is not None:
                it.setIcon(QIcon(self._pm(k, 64, 92)))
        elif k < len(self._strip_labels):
            lb = self._strip_labels[k]
            lb.setPixmap(self._pm(k, lb.width(), 0))

    def _go(self, k: int):
        n = len(self.view)
        if not n:
            self.single_lbl.setPixmap(QPixmap())
            self.single_lbl.setText("Tidak ada halaman")
            self.pos_lbl.setText("0 / 0")
            self.b_prev.setEnabled(False)
            self.b_next.setEnabled(False)
            return
        k = max(0, min(n - 1, k))
        self.view_i = k
        self.pos_lbl.setText(f"{k + 1} / {n}")
        self.b_prev.setEnabled(k > 0)
        self.b_next.setEnabled(k < n - 1)
        self.thumbs.blockSignals(True)
        self.thumbs.setCurrentRow(k)
        self.thumbs.blockSignals(False)
        if self.stack.currentIndex() == 0:
            i = self.view[k][0]
            self.prev_lbl.setText(f"Pratinjau · halaman asli #{i + 1}" if i >= 0 else "Pratinjau · halaman kredit")
            vp = self.single.viewport().size()
            self.single_lbl.setText("")
            self.single_lbl.setPixmap(self._pm(k, max(100, vp.width() - 16), max(100, vp.height() - 16)))
        else:
            self.prev_lbl.setText("Pratinjau · strip disambung (gulir)")
            if k < len(self._strip_labels):
                self.strip.verticalScrollBar().blockSignals(True)
                self.strip.verticalScrollBar().setValue(self._strip_labels[k].y())
                self.strip.verticalScrollBar().blockSignals(False)

    def _strip_scrolled(self, y):
        y += self.strip.viewport().height() // 2        # halaman di tengah layar
        for k, lb in enumerate(self._strip_labels):
            if lb.y() + lb.height() > y:
                if k != self.view_i:
                    self.view_i = k
                    self.pos_lbl.setText(f"{k + 1} / {len(self.view)}")
                    self.b_prev.setEnabled(k > 0)
                    self.b_next.setEnabled(k < len(self.view) - 1)
                    self.thumbs.blockSignals(True)
                    self.thumbs.setCurrentRow(k)
                    self.thumbs.blockSignals(False)
                break

    def _thumb_clicked(self, k):
        if k >= 0:
            self._go(k)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._resize_t.start()

    def showEvent(self, e):
        super().showEvent(e)
        self._resize_t.start()

    def _relayout(self):
        if self.stack.currentIndex() == 1:
            if self._strip_labels and abs(self._strip_labels[0].width() - self._strip_width()) > 8:
                self._build_preview()
        else:
            self._go(self.view_i)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_PageDown, Qt.Key_Right) and not self.rng.hasFocus() and self.stack.currentIndex() == 0:
            self._go(self.view_i + 1)
            return
        if e.key() in (Qt.Key_PageUp, Qt.Key_Left) and not self.rng.hasFocus() and self.stack.currentIndex() == 0:
            self._go(self.view_i - 1)
            return
        super().keyPressEvent(e)

    # ---------------------------------------------------------------- hasil
    def meta(self) -> dict:
        return {"series": self.m_series.text().strip(), "chapter": self.m_ch.text().strip(),
                "chapter_title": self.m_title.text().strip(), "author": self.m_author.text().strip(),
                "translator": self.m_tl.text().strip(), "genre": self.m_genre.text().strip(),
                "status": self.m_status.currentText(), "summary": self.m_sum.toPlainText().strip()}

    def options(self) -> dict:
        scope = "cur" if self.r_cur.isChecked() else "range" if self.r_rng.isChecked() else "all"
        return {"scope": scope, "range": self.rng.text().strip(), "use_original": self.use_orig.isChecked(),
                "fmt": self.fmt.currentData(), "kind": self.kind.currentData(),
                "img_fmt": self.img.currentData(), "quality": self.q.value(),
                "mihon_pack": self.mihon.isChecked(), "credit_page": self.c_credit.isChecked(),
                "watermark": self.c_wm.isChecked()}

    def config(self) -> dict:
        o = self.options()
        return dict(out=self.out_path, fmt=o["fmt"], kind=o["kind"], indices=[i for i, _ in self.files],
                    use_original=o["use_original"], img_fmt=o["img_fmt"], quality=o["quality"],
                    meta=self.meta(), mihon_pack=o["mihon_pack"] and o["fmt"] == "cbz",
                    credit_page=o["credit_page"] and o["fmt"] != "psd", watermark=o["watermark"] and o["fmt"] != "psd")

    def _edit_credits(self):
        from .skillsdlg import CreditsDialog
        sample = self.files[0][1] if self.files else None
        d = CreditsDialog(self.settings, self.meta(), sample, self)
        if d.exec():
            self.credits_changed = True
            self._update_ui()
            self._build_preview()

    def _do_export(self):
        if not self.files:
            return
        fmt = self.fmt.currentData()
        m = self.meta()
        base = exporter.safe_name(m["series"] or Path(self.project.pages[0].path).parent.name, "Rexxa")
        if fmt == "cbz":
            base = exporter.safe_name(f"{base} {exporter.chapter_filename(m)}")
        elif m["chapter"] and m["chapter"] not in base:
            base += f" Ch. {m['chapter']}"
        if fmt == "pdf":
            ext, flt = ".pdf", "PDF (*.pdf)"
        elif fmt == "cbz" and self.mihon.isChecked():
            ext, flt = ".zip", "Paket Mihon (*.zip)"
        elif fmt == "cbz":
            ext, flt = ".cbz", "Arsip komik (*.cbz)"
        elif fmt == "psd" and len(self.files) == 1:
            ext, flt = ".psd", "Photoshop (*.psd)"
            base = exporter.safe_name(f"{base} hal {self.files[0][0] + 1}")
        elif fmt == "psd":
            ext, flt = ".zip", "ZIP berisi PSD (*.zip)"
        else:
            ext, flt = ".zip", "ZIP (*.zip)"
        p0 = self.project.pages[self.files[0][0]]
        out_dir = self.settings.get("export_dir") or str(Path(p0.output_path or p0.path).parent)
        f, _ = QFileDialog.getSaveFileName(self, "Export As", str(Path(out_dir) / (base + ext)), flt)
        if not f:
            return
        if not f.lower().endswith(ext):
            f += ext
        self.out_path = f
        self.accept()

