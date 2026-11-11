"""Kotak judul: pembuat logo judul (dari teks, gaya mirip logo asli) atau tempel judul buatan sendiri."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QPushButton,
                               QRadioButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from core import typeset

from .skillsdlg import CHECKS, PRIMARY, _dim

FITS = [("Muat utuh di kotak", "contain"), ("Penuhi kotak (bisa terpotong)", "cover"), ("Regangkan ke kotak", "stretch")]


class _Render(QThread):
    done = Signal(int, object)

    def __init__(self, seq, fn, parent=None):
        super().__init__(parent)
        self.seq, self.fn = seq, fn

    def run(self):
        try:
            self.done.emit(self.seq, self.fn())
        except Exception as e:      # noqa: BLE001
            self.done.emit(self.seq, str(e))


class TitleDialog(QDialog):
    """Mengubah blok judul `b` (kind = "title") di halaman `page`."""

    def __init__(self, project, page, b, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kotak judul")
        self.project, self.page, self.b, self.settings = project, page, b, settings
        self.setAcceptDrops(True)
        self.resize(1040, 620)
        self.setStyleSheet(CHECKS + "QRadioButton{background:transparent}"
                           "QRadioButton::indicator{width:14px;height:14px;border:1px solid #555a66;"
                           "background:#23252b;border-radius:8px}"
                           "QRadioButton::indicator:checked{background:#ff4d6d;border-color:#ff4d6d}")
        self.image_path = b.title_image if b.title_image and Path(b.title_image).exists() else ""
        self._seq = 0
        self._jobs = []
        from core import detector
        self.src = detector.load_image(page.path)

        root = QHBoxLayout(self)
        # ---------------- kiri: pilihan
        left = QVBoxLayout()
        self.r_text = QRadioButton("Buat judul dari teks  (gaya mirip logo asli)")
        self.r_img = QRadioButton("Pakai judul buatan sendiri  (tempel gambar)")
        self.r_ai = QRadioButton("✦ Generate dengan AI gambar  (meniru gaya logo asli)")
        g = QButtonGroup(self)
        g.addButton(self.r_text)
        g.addButton(self.r_img)
        g.addButton(self.r_ai)
        (self.r_img if self.image_path else self.r_text).setChecked(True)
        left.addWidget(self.r_text)
        left.addWidget(self.r_img)
        left.addWidget(self.r_ai)
        self.stack = QStackedWidget()

        # teks
        w = QWidget()
        f = QFormLayout(w)
        f.setContentsMargins(0, 6, 0, 0)
        self.text = QLineEdit(b.translation or project.series_title or settings.get("last_series_title", ""))
        self.text.setPlaceholderText("Judul dalam bahasa tujuan")
        self.font = QComboBox()
        self.font.addItem("Font otomatis (mirip logo asli)", "")
        for fp in typeset.list_fonts():
            self.font.addItem(typeset.font_name(fp), fp)
        self.font.setCurrentIndex(max(0, self.font.findData(b.font)))
        self.font.setMaxVisibleItems(18)
        self.upper = QCheckBox("HURUF KAPITAL")
        self.upper.setChecked((b.case or "upper") == "upper")
        self.series = QCheckBox("Jadikan judul seri (dipakai juga di chapter lain)")
        self.series.setChecked(not project.series_title or project.series_title == self.text.text())
        f.addRow("Judul", self.text)
        f.addRow("Font", self.font)
        f.addRow("", self.upper)
        f.addRow("", self.series)
        f.addRow(_dim("Kata sambung (yang, di, dari, of, the…) otomatis dibuat kecil; huruf diisi tekstur "
                      "& warna logo asli."))
        self.stack.addWidget(w)

        # gambar
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 6, 0, 0)
        row = QHBoxLayout()
        b_paste = QPushButton("Tempel dari clipboard  (Ctrl+V)")
        b_paste.clicked.connect(self.paste)
        b_file = QPushButton("Pilih file…")
        b_file.clicked.connect(self.pick)
        row.addWidget(b_paste)
        row.addWidget(b_file)
        v.addLayout(row)
        self.img_info = _dim("")
        v.addWidget(self.img_info)
        f2 = QFormLayout()
        self.fit = QComboBox()
        for lab, k in FITS:
            self.fit.addItem(lab, k)
        self.fit.setCurrentIndex(max(0, self.fit.findData(b.title_fit or "contain")))
        self.scale = QSpinBox()
        self.scale.setRange(20, 300)
        self.scale.setSuffix(" %")
        self.scale.setValue(int(round(float(b.title_scale or 1.0) * 100)))
        self.clean = QCheckBox("Hapus logo asli di kotak dulu")
        self.clean.setChecked(not b.title_keep_bg)
        f2.addRow("Ukuran", self.fit)
        f2.addRow("Skala", self.scale)
        f2.addRow("", self.clean)
        v.addLayout(f2)
        v.addWidget(_dim("Buat judul di aplikasi lain (Photoshop, Canva, Ibis Paint…), salin, lalu tekan Ctrl+V "
                         "di sini. Bisa juga seret file gambar ke jendela ini. PNG transparan paling bagus."))
        v.addStretch(1)
        self.stack.addWidget(w)

        # AI gambar
        from core import imagegen
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 6, 0, 0)
        f3 = QFormLayout()
        self.ai_preset = QComboBox()
        self.ai_preset.addItems(list(imagegen.PRESETS) + ["Kustom"])
        self.ai_preset.setCurrentText(settings.get("img_preset", "ClassAI router"))
        self.ai_url = QLineEdit(settings.get("img_base_url") or imagegen.PRESETS["ClassAI router"][0])
        self.ai_key = QLineEdit(settings.get("img_api_key", ""))
        self.ai_key.setEchoMode(QLineEdit.Password)
        self.ai_key.setPlaceholderText("API key (sk_…)")
        self.ai_model = QComboBox()
        self.ai_model.setEditable(True)
        self.ai_model.addItems(["nano-banana-2", "nano-banana-pro", "nano-banana-2.1", "nano-banana",
                                "gpt-image-2", "gpt-image-1.5", "gpt-image-1"])
        self.ai_model.setCurrentText(settings.get("img_model") or imagegen.PRESETS["ClassAI router"][1])
        self.ai_n = QSpinBox()
        self.ai_n.setRange(1, 4)
        self.ai_n.setValue(int(settings.get("img_n", 2)))
        self.ai_hint = QLineEdit(settings.get("img_hint", ""))
        self.ai_hint.setPlaceholderText("(opsional) mis. kata 'Villain' merah menyala")
        self.ai_ref = QCheckBox("Kirim logo asli sebagai contoh gaya")
        self.ai_ref.setChecked(True)
        self.ai_bg = QCheckBox("Latar polos → transparan otomatis")
        self.ai_bg.setChecked(True)
        self.ai_preset.currentTextChanged.connect(self._ai_preset)
        f3.addRow("Layanan", self.ai_preset)
        f3.addRow("Base URL", self.ai_url)
        f3.addRow("API key", self.ai_key)
        f3.addRow("Model", self.ai_model)
        f3.addRow("Jumlah", self.ai_n)
        f3.addRow("Catatan", self.ai_hint)
        f3.addRow("", self.ai_ref)
        f3.addRow("", self.ai_bg)
        v.addLayout(f3)
        self.b_gen = QPushButton("✦ Generate judul")
        self.b_gen.setStyleSheet(PRIMARY)
        self.b_gen.clicked.connect(self._generate)
        v.addWidget(self.b_gen)
        self.ai_list = QListWidget()
        self.ai_list.setViewMode(QListView.IconMode)
        self.ai_list.setIconSize(QSize(180, 120))
        self.ai_list.setMovement(QListView.Static)
        self.ai_list.setResizeMode(QListView.Adjust)
        self.ai_list.setMinimumHeight(140)
        self.ai_list.itemClicked.connect(self._pick_ai)
        v.addWidget(self.ai_list, 1)
        v.addWidget(_dim("Teks judul diambil dari kolom Judul (mode teks). Setiap gambar memakai kredit "
                         "layanan AI. AI kadang salah eja — buat beberapa versi lalu pilih yang benar. "
                         "Klik hasil untuk memakainya."))
        self.stack.addWidget(w)
        self._ai_imgs = []
        left.addWidget(self.stack)
        left.addStretch(1)
        self.status = _dim("")
        left.addWidget(self.status)
        btn = QHBoxLayout()
        btn.addStretch(1)
        cancel = QPushButton("Batal")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("Pakai judul ini")
        self.ok.setStyleSheet(PRIMARY)
        self.ok.clicked.connect(self._accept)
        btn.addWidget(cancel)
        btn.addWidget(self.ok)
        left.addLayout(btn)
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(430)
        root.addWidget(lw)

        # ---------------- kanan: pratinjau sebelum / sesudah
        right = QVBoxLayout()
        right.addWidget(_dim("Sebelum"))
        self.before = QLabel()
        self.after = QLabel()
        for l in (self.before, self.after):
            l.setAlignment(Qt.AlignCenter)
            l.setMinimumHeight(200)
            l.setStyleSheet("background:#0f1013;border:1px solid #26282f;border-radius:6px")
        right.addWidget(self.before, 1)
        right.addWidget(_dim("Sesudah"))
        right.addWidget(self.after, 1)
        root.addLayout(right, 1)

        QShortcut(QKeySequence.Paste, self, activated=self.paste)
        self._t = QTimer(self, singleShot=True, interval=300, timeout=self._render)
        for sig in (self.r_text.toggled, self.r_ai.toggled, self.upper.toggled, self.clean.toggled):
            sig.connect(lambda *_: self._changed())
        for sig in (self.font.currentIndexChanged, self.fit.currentIndexChanged, self.scale.valueChanged):
            sig.connect(lambda *_: self._changed())
        self.text.textChanged.connect(lambda *_: self._changed())
        self._changed()

    # ---------------------------------------------------------------- gambar sendiri
    def _set_image(self, src):
        from core import titlelogo
        try:
            self.image_path = titlelogo.store_image(src)
        except Exception as e:      # noqa: BLE001
            self.status.setText(f"<span style='color:#ff6680'>Gambar tidak bisa dibaca: {e}</span>")
            return
        self.r_img.setChecked(True)
        self._changed()

    def paste(self):
        if self.text.hasFocus() and self.r_text.isChecked():
            self.text.paste()
            return
        cb = QApplication.clipboard()
        md = cb.mimeData()
        if md is not None and md.hasImage():
            img = cb.image()
            if not img.isNull():
                from PySide6.QtCore import QBuffer, QIODevice
                buf = QBuffer()
                buf.open(QIODevice.WriteOnly)
                img.save(buf, "PNG")
                self._set_image(bytes(buf.data()))
                return
        if md is not None and md.hasUrls():
            for u in md.urls():
                if u.isLocalFile():
                    self._set_image(u.toLocalFile())
                    return
        self.status.setText("Clipboard tidak berisi gambar. Salin gambar judulmu dulu (Ctrl+C) di aplikasi lain.")

    def pick(self):
        f, _ = QFileDialog.getOpenFileName(self, "Pilih gambar judul", "", "Gambar (*.png *.webp *.jpg *.jpeg *.bmp)")
        if f:
            self._set_image(f)

    def dragEnterEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or md.hasImage():
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        for u in md.urls():
            if u.isLocalFile():
                self._set_image(u.toLocalFile())
                return

    # ---------------------------------------------------------------- AI gambar
    def _ai_preset(self, name):
        from core import imagegen
        if name in imagegen.PRESETS:
            url, model = imagegen.PRESETS[name]
            self.ai_url.setText(url)
            self.ai_model.setCurrentText(model)

    def _ai_save(self):
        self.settings.update(img_preset=self.ai_preset.currentText(), img_base_url=self.ai_url.text().strip(),
                             img_api_key=self.ai_key.text().strip(), img_model=self.ai_model.currentText().strip(),
                             img_n=self.ai_n.value(), img_hint=self.ai_hint.text().strip())

    def _generate(self):
        from core import imagegen
        title = self.text.text().strip()
        if not title:
            self.status.setText("Isi dulu kolom Judul (di mode 'Buat judul dari teks').")
            return
        if not self.ai_key.text().strip():
            self.status.setText("Isi API key layanan AI gambar dulu.")
            return
        self._ai_save()
        st = dict(self.settings)
        n, use_ref, clear_bg = self.ai_n.value(), self.ai_ref.isChecked(), self.ai_bg.isChecked()
        hint = self.ai_hint.text().strip()
        ref = None
        if use_ref:
            x0, y0, x1, y1 = self._crop_rect()
            ref = imagegen.to_png(self.src[y0:y1, x0:x1])

        def work():
            prompt = imagegen.title_prompt(title, hint, has_ref=ref is not None)
            raw = imagegen.edit(st, ref, prompt, n) if ref is not None else imagegen.generate(st, prompt, n)
            out = []
            from PIL import Image
            import io
            for d in raw:
                out.append(imagegen.remove_plain_bg(d) if clear_bg else Image.open(io.BytesIO(d)).convert("RGBA"))
            return out

        self.b_gen.setEnabled(False)
        self.status.setText(f"AI sedang membuat {n} judul… (bisa ±10–60 detik)")
        from .skillsdlg import _Job
        self._gen = _Job(work, self)
        self._gen.done.connect(self._generated)
        self._jobs.append(self._gen)
        self._gen.start()

    def _generated(self, imgs, err):
        self.b_gen.setEnabled(True)
        if err:
            self.status.setText(f"<span style='color:#ff6680'>{err}</span>")
            return
        for im in imgs or []:
            self._ai_imgs.append(im)
            q = im.convert("RGBA")
            data = q.tobytes("raw", "RGBA")
            qi = QImage(data, q.width, q.height, q.width * 4, QImage.Format_RGBA8888).copy()
            it = QListWidgetItem(QIcon(QPixmap.fromImage(qi)), f"Hasil {len(self._ai_imgs)}")
            it.setData(Qt.UserRole, len(self._ai_imgs) - 1)
            self.ai_list.addItem(it)
        self.status.setText(f"{len(imgs or [])} judul dibuat. Klik salah satu untuk memakainya.")

    def _pick_ai(self, it):
        k = it.data(Qt.UserRole)
        if k is None or k >= len(self._ai_imgs):
            return
        from core import titlelogo
        self.image_path = titlelogo.store_image(self._ai_imgs[k])
        self.status.setText(f"Hasil {k + 1} dipakai — atur ukuran / skala di mode 'Pakai judul buatan sendiri'.")
        self._changed()

    # ---------------------------------------------------------------- pratinjau
    def _crop_rect(self):
        b = self.b
        H, W = self.src.shape[:2]
        m = int(max(b.w, b.h) * 0.15)
        return max(0, b.x - m), max(0, b.y - m), min(W, b.x + b.w + m), min(H, b.y + b.h + m)

    @staticmethod
    def _pix(bgr, lbl):
        rgb = np.ascontiguousarray(bgr[..., ::-1])
        h, w = rgb.shape[:2]
        q = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888).copy()
        return QPixmap.fromImage(q).scaled(max(50, lbl.width() - 8), max(50, lbl.height() - 8),
                                           Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _changed(self):
        self.stack.setCurrentIndex(2 if self.r_ai.isChecked() else 1 if self.r_img.isChecked() else 0)
        if self.image_path:
            try:
                from PIL import Image
                with Image.open(self.image_path) as im:
                    self.img_info.setText(f"Gambar: {im.width} × {im.height} px"
                                          + (" · transparan" if im.mode in ("RGBA", "LA", "P") else ""))
            except Exception:
                self.img_info.setText("")
        else:
            self.img_info.setText("Belum ada gambar.")
        self.ok.setEnabled(bool(self.image_path) if (self.r_img.isChecked() or self.r_ai.isChecked())
                           else bool(self.text.text().strip()))
        self._t.start()

    def _render(self):
        x0, y0, x1, y1 = self._crop_rect()
        self.before.setPixmap(self._pix(self.src[y0:y1, x0:x1], self.before))
        self._seq += 1
        seq, src, b, cfg = self._seq, self.src, self.b, self._cfg()
        font = cfg["font"] or b.font or typeset.default_font(self.project.target_lang)

        def work():
            from core import titlelogo
            rect = [b.x, b.y, b.w, b.h]
            mask = titlelogo.mask_in_rect(src, rect)
            if cfg["mode"] == "image":
                if not cfg["image"]:
                    return src[y0:y1, x0:x1]
                out = titlelogo.paste_title(src, cfg["image"], rect, mask, cfg["fit"], cfg["scale"],
                                            clean=cfg["clean"])
            else:
                if not cfg["text"]:
                    return src[y0:y1, x0:x1]
                out = titlelogo.render_title(src, cfg["text"], rect, mask, font, upper=cfg["upper"])
            return out[y0:y1, x0:x1]

        self.status.setText("Membuat pratinjau…")
        j = _Render(seq, work, self)
        j.done.connect(self._rendered)
        self._jobs.append(j)
        j.finished.connect(lambda j=j: self._jobs.remove(j) if j in self._jobs else None)
        j.start()

    def _rendered(self, seq, res):
        if seq != self._seq:
            return
        if isinstance(res, str):
            self.status.setText(f"<span style='color:#ff6680'>{res}</span>")
            return
        self.status.setText("")
        self.after.setPixmap(self._pix(res, self.after))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._t.start()

    # ---------------------------------------------------------------- simpan
    def _cfg(self):
        return {"mode": "image" if (self.r_img.isChecked() or self.r_ai.isChecked()) else "text",
                "image": self.image_path,
                "fit": self.fit.currentData(), "scale": self.scale.value() / 100.0, "clean": self.clean.isChecked(),
                "text": self.text.text().strip(), "font": self.font.currentData(), "upper": self.upper.isChecked()}

    def _accept(self):
        self._ai_save()
        c = self._cfg()
        b = self.b
        if c["mode"] == "image":
            b.title_image = c["image"]
            b.title_fit, b.title_scale, b.title_keep_bg = c["fit"], float(c["scale"]), not c["clean"]
        else:
            b.title_image = ""
            b.translation = c["text"]
            if c["font"]:
                b.font = c["font"]
            b.case = "upper" if c["upper"] else "none"
            if self.series.isChecked():
                self.project.series_title = c["text"]
                self.settings["last_series_title"] = c["text"]
        b.source = b.source or "[logo judul]"
        self.accept()

    def done(self, r):
        for j in list(self._jobs):
            j.wait(3000)
        super().done(r)

