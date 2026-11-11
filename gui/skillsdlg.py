"""Dialog skill: Memori cerita, Proofread, Kredit & watermark."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from core import skills

from .alert import MessageBox as QMessageBox

PRIMARY = ("QPushButton{background:#ff4d6d;color:white;font-weight:600;border:none;border-radius:6px;"
           "padding:6px 16px}QPushButton:hover{background:#ff6680}"
           "QPushButton:disabled{background:#5a3640;color:#b9a3a9}")
CHECKS = ("QCheckBox{background:transparent}"
          "QCheckBox::indicator{width:14px;height:14px;border:1px solid #555a66;background:#23252b;border-radius:3px}"
          "QCheckBox::indicator:checked{background:#ff4d6d;border-color:#ff4d6d}")


class _Job(QThread):
    """Jalankan fungsi lama (permintaan LLM) di latar; hasil dikirim ke thread tampilan."""
    done = Signal(object, str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn(), "")
        except Exception as e:      # noqa: BLE001  (pesan ditampilkan ke pengguna)
            self.done.emit(None, str(e))


def _dim(text):
    l = QLabel(text)
    l.setObjectName("dim")
    l.setWordWrap(True)
    return l


# ====================================================================== memori cerita
class StoryDialog(QDialog):
    COLS = [("name", "Nama (terjemahan)"), ("source", "Nama di raw"), ("gender", "Gender"),
            ("call", "Panggilan / kata ganti"), ("speech", "Gaya bicara"), ("notes", "Catatan")]

    def __init__(self, project, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Memori cerita")
        self.project, self.settings = project, settings
        self.resize(980, 600)
        self.setStyleSheet(CHECKS)
        v = QVBoxLayout(self)
        key = skills.series_key(project)
        v.addWidget(_dim(
            "AI mengingat tokoh, gender, cara memanggil (aku/kamu, gue/lo, kak…) dan gaya bicara tiap tokoh, "
            "supaya terjemahan konsisten di semua halaman. Disimpan juga untuk seri "
            f"<b>{key or '(belum ada judul)'}</b>, jadi chapter berikutnya dengan judul seri yang sama "
            "langsung memakainya. Nama di raw juga dipakai sebagai glosarium untuk Google / DeepL."))
        self.tbl = QTableWidget(0, len(self.COLS))
        self.tbl.setHorizontalHeaderLabels([c[1] for c in self.COLS])
        hh = self.tbl.horizontalHeader()
        for i in range(len(self.COLS)):
            hh.setSectionResizeMode(i, QHeaderView.Stretch if i >= 3 else QHeaderView.Interactive)
        hh.resizeSection(0, 150)
        hh.resizeSection(1, 130)
        hh.resizeSection(2, 110)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        v.addWidget(self.tbl, 1)
        row = QHBoxLayout()
        b_add = QPushButton("+ Tambah tokoh")
        b_add.clicked.connect(lambda: self._add({}))
        b_del = QPushButton("Hapus terpilih")
        b_del.clicked.connect(self._del)
        self.b_learn = QPushButton("✦ Pelajari dari chapter ini (AI)")
        self.b_learn.setToolTip("AI membaca semua teks chapter ini lalu mengisi / melengkapi daftar tokoh.\n"
                                "Butuh mesin LLM (Pengaturan → Terjemahan → LLM).")
        self.b_learn.clicked.connect(self._learn)
        row.addWidget(b_add)
        row.addWidget(b_del)
        row.addStretch(1)
        row.addWidget(self.b_learn)
        v.addLayout(row)
        v.addWidget(QLabel("<b>Catatan cerita</b> (latar, istilah, hubungan antar tokoh)"))
        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(80)
        self.notes.setPlaceholderText("mis. Latar: akademi sihir. 'Mana' tidak diterjemahkan. Duke = Adipati.")
        v.addWidget(self.notes)
        opt = QHBoxLayout()
        self.use = QCheckBox("Pakai memori saat menerjemahkan")
        self.use.setChecked(bool(settings.get("story_memory", True)))
        self.ctx = QCheckBox("Sertakan akhir halaman sebelumnya (LLM)")
        self.ctx.setToolTip("Beberapa baris terakhir halaman sebelumnya ikut dikirim supaya percakapan nyambung.")
        self.ctx.setChecked(bool(settings.get("story_context", True)))
        opt.addWidget(self.use)
        opt.addWidget(self.ctx)
        opt.addStretch(1)
        v.addLayout(opt)
        self.status = _dim("")
        v.addWidget(self.status)
        btn = QHBoxLayout()
        btn.addStretch(1)
        cancel = QPushButton("Batal")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Simpan")
        ok.setStyleSheet(PRIMARY)
        ok.clicked.connect(self._save)
        btn.addWidget(cancel)
        btn.addWidget(ok)
        v.addLayout(btn)
        self._fill(skills.story_of(project))

    def _fill(self, story):
        self.tbl.setRowCount(0)
        for c in story["characters"]:
            self._add(c)
        self.notes.setPlainText(story.get("notes", ""))

    def _add(self, c):
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        for i, (k, _lab) in enumerate(self.COLS):
            if k == "gender":
                cb = QComboBox()
                cb.addItems(["?", "Laki-laki", "Perempuan", "Lainnya"])
                cb.setCurrentIndex(max(0, skills.GENDERS.index(c.get(k, "")) if c.get(k, "") in skills.GENDERS else 0))
                self.tbl.setCellWidget(r, i, cb)
            else:
                self.tbl.setItem(r, i, QTableWidgetItem(c.get(k, "")))
        if not c:
            self.tbl.setCurrentCell(r, 0)
            self.tbl.editItem(self.tbl.item(r, 0))

    def _del(self):
        for r in sorted({i.row() for i in self.tbl.selectedIndexes()}, reverse=True):
            self.tbl.removeRow(r)

    def story(self) -> dict:
        chars = []
        for r in range(self.tbl.rowCount()):
            c = {}
            for i, (k, _lab) in enumerate(self.COLS):
                if k == "gender":
                    c[k] = skills.GENDERS[self.tbl.cellWidget(r, i).currentIndex()]
                else:
                    it = self.tbl.item(r, i)
                    c[k] = it.text().strip() if it else ""
            if c["name"]:
                chars.append(c)
        return {"characters": chars, "notes": self.notes.toPlainText().strip()}

    def _learn(self):
        if self.settings.get("translate_engine") != "llm" and not self.settings.get("llm_base_url"):
            QMessageBox.information(self, "Memori cerita", "Fitur ini butuh LLM. Atur dulu di Pengaturan → "
                                                           "Terjemahan → LLM (mis. Gemini).")
            return
        self.project.story = self.story()
        proj, st = self.project, dict(self.settings)
        self.b_learn.setEnabled(False)
        self.status.setText("AI sedang membaca chapter…")
        self._job = _Job(lambda: skills.learn(proj, st), self)
        self._job.done.connect(self._learned)
        self._job.start()

    def _learned(self, story, err):
        self.b_learn.setEnabled(True)
        if err:
            self.status.setText(f"<span style='color:#ff6680'>Gagal: {err}</span>")
            return
        before = self.tbl.rowCount()
        self._fill(story)
        self.status.setText(f"Selesai: {self.tbl.rowCount()} tokoh ({self.tbl.rowCount() - before:+d}). "
                            "Periksa & perbaiki bila perlu, lalu Simpan.")

    def _save(self):
        self.project.story = self.story()
        self.settings["story_memory"] = self.use.isChecked()
        self.settings["story_context"] = self.ctx.isChecked()
        try:
            skills.save_series(self.project)
        except OSError:
            pass
        self.accept()


# ====================================================================== proofread
class ProofreadDialog(QDialog):
    """Daftar masalah terjemahan. Klik baris = lompat ke balon; 'Terapkan' = pakai saran."""
    jump = Signal(int, str)            # indeks halaman, id balon

    KIND = {"kosong": "Kosong", "sama": "Sama", "ketik": "Ketik", "tanda": "Tanda baca", "panjang": "Kepanjangan",
            "nama": "Nama", "ai": "AI"}

    def __init__(self, project, settings, cur, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Proofread")
        self.project, self.settings, self.cur = project, settings, cur
        self.changed: set[int] = set()
        self.issues: list[dict] = []
        self.resize(1000, 620)
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        self.scope = QComboBox()
        self.scope.addItem("Halaman ini", "cur")
        self.scope.addItem("Semua halaman", "all")
        self.scope.currentIndexChanged.connect(lambda _i: self._local())
        top.addWidget(QLabel("Cek:"))
        top.addWidget(self.scope)
        top.addStretch(1)
        self.b_ai = QPushButton("✦ Cek dengan AI")
        self.b_ai.setToolTip("AI memeriksa salah arti, kalimat kaku, typo, nama/panggilan tidak konsisten,\n"
                             "dan teks kepanjangan, lalu memberi saran. Butuh mesin LLM.")
        self.b_ai.clicked.connect(self._ai)
        top.addWidget(self.b_ai)
        v.addLayout(top)
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Hal.", "Balon", "Jenis", "Masalah", "Saran"])
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.Stretch)
        for i, w in ((0, 46), (1, 52), (2, 92)):
            hh.resizeSection(i, w)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setWordWrap(True)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.tbl.cellClicked.connect(self._clicked)
        v.addWidget(self.tbl, 1)
        self.detail = _dim("")
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(self.detail)
        bot = QHBoxLayout()
        self.status = _dim("")
        bot.addWidget(self.status, 1)
        self.b_apply = QPushButton("Terapkan saran terpilih")
        self.b_apply.clicked.connect(lambda: self._apply(selected=True))
        self.b_all = QPushButton("Terapkan semua saran")
        self.b_all.clicked.connect(lambda: self._apply(selected=False))
        close = QPushButton("Selesai")
        close.setStyleSheet(PRIMARY)
        close.clicked.connect(self.accept)
        for b in (self.b_apply, self.b_all, close):
            bot.addWidget(b)
        v.addLayout(bot)
        self._local()

    def _pages(self):
        return [self.cur] if self.scope.currentData() == "cur" and self.cur >= 0 else list(range(len(self.project.pages)))

    def _local(self):
        self.issues = [i for i in self.issues if i["kind"] == "ai" and i["page"] in self._pages()]
        self.issues = skills.local_checks(self.project, self._pages()) + self.issues
        self._show()

    def _show(self):
        self.tbl.setRowCount(0)
        for it in self.issues:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            vals = [str(it["page"] + 1), str(it["num"]), self.KIND.get(it["kind"], it["kind"]), it["msg"], it["fix"]]
            for c, val in enumerate(vals):
                cell = QTableWidgetItem(val)
                if c != 4:
                    cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                if it["kind"] == "ai" and c == 2:
                    cell.setForeground(Qt.magenta)
                self.tbl.setItem(r, c, cell)
        self.tbl.resizeRowsToContents()
        n_fix = sum(1 for i in self.issues if i["fix"])
        self.status.setText(f"{len(self.issues)} catatan · {n_fix} punya saran"
                            if self.issues else "Tidak ada masalah ditemukan. 👍")
        self.b_all.setEnabled(n_fix > 0)

    def _clicked(self, r, _c):
        if 0 <= r < len(self.issues):
            it = self.issues[r]
            self.detail.setText(f"<b>Asli:</b> {it['src']}<br><b>Terjemahan:</b> {it['tl']}")
            self.jump.emit(it["page"], it["block"])

    def _ai(self):
        if not self.settings.get("llm_base_url"):
            QMessageBox.information(self, "Proofread", "Cek AI butuh LLM. Atur dulu di Pengaturan → "
                                                       "Terjemahan → LLM (mis. Gemini).")
            return
        pages = [p for p in self._pages() if any((b.translation or "").strip() for b in self.project.pages[p].blocks)]
        if not pages:
            return
        proj, st = self.project, dict(self.settings)
        self.b_ai.setEnabled(False)
        self.status.setText(f"AI memeriksa {len(pages)} halaman…")

        def work():
            out = []
            for p in pages:
                out += skills.ai_review(proj, st, p)
            return out

        self._job = _Job(work, self)
        self._job.done.connect(self._ai_done)
        self._job.start()

    def _ai_done(self, res, err):
        self.b_ai.setEnabled(True)
        if err:
            self.status.setText(f"<span style='color:#ff6680'>Gagal: {err}</span>")
            return
        self.issues = [i for i in self.issues if i["kind"] != "ai"] + (res or [])
        self.issues.sort(key=lambda i: (i["page"], i["num"]))
        self._show()

    def _apply(self, selected):
        rows = sorted({i.row() for i in self.tbl.selectedIndexes()}) if selected else range(len(self.issues))
        done = []
        for r in rows:
            it = self.issues[r]
            cell = self.tbl.item(r, 4)
            fix = (cell.text() if cell else it["fix"]).strip()
            if not fix:
                continue
            page = self.project.pages[it["page"]]
            b = next((x for x in page.blocks if x.id == it["block"]), None)
            if b is None:
                continue
            b.translation = fix
            self.changed.add(it["page"])
            done.append(r)
        if done:
            self.issues = [i for k, i in enumerate(self.issues) if k not in set(done)]
            self._show()
            self.status.setText(f"{len(done)} saran diterapkan · halaman terkait dirender ulang setelah dialog ditutup.")


# ====================================================================== kredit & watermark
class CreditsDialog(QDialog):
    def __init__(self, settings, meta=None, sample=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Halaman kredit & watermark")
        self.settings, self.meta, self.sample = settings, dict(meta or {}), sample
        cfg = skills.credits_cfg(settings)
        self.resize(940, 640)
        self.setStyleSheet(CHECKS)
        root = QHBoxLayout(self)
        left = QVBoxLayout()
        f = QFormLayout()
        self.team = QLineEdit(cfg["team"])
        self.team.setPlaceholderText("Nama tim / grup scanlation")
        self.roles = QPlainTextEdit(cfg["roles"])
        self.roles.setFixedHeight(120)
        self.roles.setPlaceholderText("Peran: Nama  (satu per baris)")
        self.msg = QPlainTextEdit(cfg["message"])
        self.msg.setFixedHeight(56)
        self.logo = QLineEdit(cfg["logo"])
        self.logo.setPlaceholderText("(opsional) logo tim .png")
        lb = QPushButton("…")
        lb.setFixedWidth(30)
        lb.clicked.connect(self._pick_logo)
        lw = QWidget()
        lh = QHBoxLayout(lw)
        lh.setContentsMargins(0, 0, 0, 0)
        lh.addWidget(self.logo, 1)
        lh.addWidget(lb)
        self.pos = QComboBox()
        for k, lab in (("end", "Di akhir chapter"), ("start", "Di awal chapter"), ("both", "Awal & akhir")):
            self.pos.addItem(lab, k)
        self.pos.setCurrentIndex(max(0, self.pos.findData(cfg["position"])))
        self.dark = QCheckBox("Latar gelap")
        self.dark.setChecked(bool(cfg["dark"]))
        f.addRow("Tim", self.team)
        f.addRow("Peran", self.roles)
        f.addRow("Pesan", self.msg)
        f.addRow("Logo", lw)
        f.addRow("Posisi", self.pos)
        f.addRow("", self.dark)
        left.addWidget(QLabel("<b>Halaman kredit</b>"))
        left.addLayout(f)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#2e3038")
        left.addWidget(line)
        left.addWidget(QLabel("<b>Watermark</b> (teks kecil di setiap halaman)"))
        g = QFormLayout()
        self.wm_text = QLineEdit(cfg["wm_text"])
        self.wm_text.setPlaceholderText("kosong = pakai nama tim")
        self.wm_pos = QComboBox()
        for k, lab in skills.WM_POS.items():
            self.wm_pos.addItem(lab, k)
        self.wm_pos.setCurrentIndex(max(0, self.wm_pos.findData(cfg["wm_pos"])))
        self.wm_op = QSpinBox()
        self.wm_op.setRange(5, 100)
        self.wm_op.setSuffix(" %")
        self.wm_op.setValue(int(cfg["wm_opacity"]))
        self.wm_size = QDoubleSpinBox()
        self.wm_size.setRange(0.8, 8.0)
        self.wm_size.setSingleStep(0.2)
        self.wm_size.setSuffix(" %")
        self.wm_size.setValue(float(cfg["wm_size"]))
        g.addRow("Teks", self.wm_text)
        g.addRow("Posisi", self.wm_pos)
        g.addRow("Opacity", self.wm_op)
        g.addRow("Ukuran", self.wm_size)
        left.addLayout(g)
        left.addWidget(_dim("Halaman kredit & watermark ditambahkan saat <b>Export As</b> (centang di sana). "
                            "Gambar hasil terjemahan di folder tidak diubah."))
        left.addStretch(1)
        btn = QHBoxLayout()
        btn.addStretch(1)
        cancel = QPushButton("Batal")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Simpan")
        ok.setStyleSheet(PRIMARY)
        ok.clicked.connect(self._save)
        btn.addWidget(cancel)
        btn.addWidget(ok)
        left.addLayout(btn)
        lwid = QWidget()
        lwid.setLayout(left)
        lwid.setFixedWidth(430)
        root.addWidget(lwid)

        pv = QVBoxLayout()
        pv.addWidget(_dim("Pratinjau"))
        self.prev_credit = QLabel()
        self.prev_credit.setAlignment(Qt.AlignCenter)
        self.prev_wm = QLabel()
        self.prev_wm.setAlignment(Qt.AlignCenter)
        for l in (self.prev_credit, self.prev_wm):
            l.setStyleSheet("background:#0f1013;border:1px solid #26282f;border-radius:6px")
            l.setMinimumSize(QSize(200, 200))
        h = QHBoxLayout()
        h.addWidget(self.prev_credit, 1)
        h.addWidget(self.prev_wm, 1)
        pv.addLayout(h, 1)
        root.addLayout(pv, 1)

        self._t = QTimer(self, singleShot=True, interval=200, timeout=self._preview)
        for w in (self.team, self.logo, self.wm_text):
            w.textChanged.connect(lambda *_: self._t.start())
        for w in (self.roles, self.msg):
            w.textChanged.connect(self._t.start)
        for w in (self.pos, self.wm_pos):
            w.currentIndexChanged.connect(lambda *_: self._t.start())
        self.dark.toggled.connect(lambda *_: self._t.start())
        self.wm_op.valueChanged.connect(lambda *_: self._t.start())
        self.wm_size.valueChanged.connect(lambda *_: self._t.start())
        QTimer.singleShot(0, self._preview)

    def cfg(self) -> dict:
        c = skills.credits_cfg(self.settings)
        c.update(team=self.team.text().strip(), roles=self.roles.toPlainText(), message=self.msg.toPlainText(),
                 logo=self.logo.text().strip(), position=self.pos.currentData(), dark=self.dark.isChecked(),
                 wm_text=self.wm_text.text().strip(), wm_pos=self.wm_pos.currentData(),
                 wm_opacity=self.wm_op.value(), wm_size=self.wm_size.value())
        return c

    def _pick_logo(self):
        f, _ = QFileDialog.getOpenFileName(self, "Pilih logo", "", "Gambar (*.png *.jpg *.jpeg *.webp)")
        if f:
            self.logo.setText(f)

    @staticmethod
    def _pix(im, w, h):
        im = im.convert("RGB")
        data = im.tobytes("raw", "RGB")
        q = QImage(data, im.width, im.height, im.width * 3, QImage.Format_RGB888).copy()
        return QPixmap.fromImage(q).scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _preview(self):
        from PIL import Image
        c = self.cfg()
        size = (1000, 1420)
        sample = None
        if self.sample:
            try:
                sample = Image.open(self.sample)
                sample.load()
                size = sample.size if sample.height < sample.width * 2.2 else (sample.width, int(sample.width * 1.4))
            except Exception:
                sample = None
        cp = skills.credit_page(c, size, self.meta)
        w, h = max(200, self.prev_credit.width() - 10), max(200, self.prev_credit.height() - 10)
        self.prev_credit.setPixmap(self._pix(cp, w, h))
        if sample is None:
            sample = Image.new("RGB", size, (235, 235, 238))
        wm = skills.watermark(sample, c)
        crop = wm.crop((wm.width // 2, max(0, wm.height - wm.width), wm.width, wm.height)) \
            if c["wm_pos"] in ("br", "bl") else wm
        if c["wm_pos"] == "bl":
            crop = wm.crop((0, max(0, wm.height - wm.width), wm.width // 2, wm.height))
        self.prev_wm.setPixmap(self._pix(crop, w, h))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._t.start()

    def _save(self):
        c = self.cfg()
        keep = skills.credits_cfg(self.settings)
        c["page"], c["watermark"] = keep.get("page", False), keep.get("watermark", False)
        self.settings["credits"] = c
        self.accept()
