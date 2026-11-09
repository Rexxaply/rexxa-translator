"""Cek & pasang update dari GitHub Release (di latar belakang, tidak membuat aplikasi macet)."""
from __future__ import annotations

import threading
from datetime import date

from PySide6.QtCore import QObject, QProcess, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from core import pipeline, selfupdate, version


def _mb(n):
    return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{max(1, n // 1024)} KB"


class UpdateChecker(QObject):
    done = Signal(dict, str, bool)          # info, error, manual
    dl_progress = Signal(int, int)
    dl_done = Signal(str, str)              # path, error

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.done.connect(self._on_done)
        self.dl_progress.connect(self._on_dl_progress)
        self.dl_done.connect(self._on_dl_done)
        self._busy = False
        self._cancel = False
        self._dlg = None
        self._pending = None

    def source(self):
        # selalu repo resmi; isian lama dari versi sebelumnya diabaikan
        return version.DEFAULT_REPO

    # ------------------------------------------------------------------ cek
    def check(self, manual: bool = False):
        st = self.window.settings
        if self._busy:
            return
        self._busy = True
        src = self.source()
        if manual:
            self.window.status_lbl.setText("Mengecek update…")

        def work():
            try:
                self.done.emit(version.fetch_latest(src), "", manual)
            except Exception as e:
                self.done.emit({}, str(e), manual)

        threading.Thread(target=work, daemon=True).start()

    def _on_done(self, info: dict, err: str, manual: bool):
        self._busy = False
        st, w = self.window.settings, self.window
        if err:
            w.log(f"Cek update gagal: {err}")
            if manual:
                QMessageBox.warning(w, "Cek update", f"Gagal mengecek update:\n{err}")
            return
        st["update_last_check"] = date.today().isoformat()
        pipeline.save_settings(st)

        remote = (info.get("version") or "").lstrip("vV")
        if not version.is_newer(remote):
            w.log(f"Rexxa Translator sudah versi terbaru ({version.__version__}).")
            if manual:
                QMessageBox.information(w, "Cek update", f"Kamu sudah memakai versi terbaru ({version.__version__}).")
            return
        if not manual and st.get("update_skip_version") == remote:
            return
        self._offer(info, remote)

    def _offer(self, info, remote):
        w = self.window
        kind = version.update_kind(info)
        notes = (info.get("notes") or "").strip()
        size = (info.get(kind) or {}).get("size", 0) if kind in ("app", "full") else 0
        how = {
            "app": f"Update cepat — hanya kode aplikasi ({_mb(size)}). Aplikasi akan restart sendiri.",
            "full": f"Update penuh — mesin aplikasi ikut diperbarui ({_mb(size)}). "
                    "Aplikasi akan tertutup, dipasang, lalu terbuka lagi.",
            "manual": "Unduh versi baru dari halaman rilis, lalu ekstrak menimpa folder lama.",
        }[kind]
        box = QMessageBox(w)
        box.setWindowTitle("Update tersedia")
        box.setIcon(QMessageBox.Information)
        box.setText(f"<b>Rexxa Translator {remote}</b> sudah tersedia.<br>Versi kamu: {version.__version__}")
        body = (notes[:1500] + ("…" if len(notes) > 1500 else "") + "\n\n") if notes else ""
        box.setInformativeText(body + how + "\nPengaturan, API key, dan font kamu tetap aman.")
        b_go = box.addButton("Update sekarang" if kind != "manual" else "Buka halaman rilis", QMessageBox.AcceptRole)
        b_skip = box.addButton("Lewati versi ini", QMessageBox.RejectRole)
        box.addButton("Nanti", QMessageBox.RejectRole)
        box.setDefaultButton(b_go)
        box.exec()
        if box.clickedButton() is b_go:
            if kind == "manual":
                QDesktopServices.openUrl(QUrl(info.get("page") or f"https://github.com/{self.source()}/releases"))
            else:
                self._start_download(info, kind, remote)
        elif box.clickedButton() is b_skip:
            self.window.settings["update_skip_version"] = remote
            pipeline.save_settings(self.window.settings)

    # ------------------------------------------------------------------ unduh & pasang
    def _start_download(self, info, kind, remote):
        w = self.window
        if w.thread:
            QMessageBox.information(w, "Update", "Tunggu proses penerjemahan selesai dulu, lalu coba lagi.")
            return
        if w.project.pages and w.project.file:
            w.project.save()
        asset = info[kind]
        self._pending = (kind, remote)
        self._cancel = False
        self._dlg = QProgressDialog(f"Mengunduh Rexxa Translator {remote}…", "Batal", 0, 100, w)
        self._dlg.setWindowTitle("Update")
        self._dlg.setWindowModality(Qt.WindowModal)
        self._dlg.setMinimumDuration(0)
        self._dlg.canceled.connect(lambda: setattr(self, "_cancel", True))
        self._dlg.show()

        def work():
            try:
                p = selfupdate.download(asset, lambda a, b: self.dl_progress.emit(a, b), lambda: self._cancel)
                self.dl_done.emit(str(p), "")
            except Exception as e:
                self.dl_done.emit("", str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_dl_progress(self, done, total):
        if self._dlg:
            if total:
                self._dlg.setMaximum(100)
                self._dlg.setValue(int(done * 100 / total))
                self._dlg.setLabelText(f"Mengunduh… {_mb(done)} / {_mb(total)}")
            else:
                self._dlg.setMaximum(0)
                self._dlg.setLabelText(f"Mengunduh… {_mb(done)}")

    def _on_dl_done(self, path, err):
        w = self.window
        if self._dlg:
            self._dlg.close()
            self._dlg = None
        if err:
            if not self._cancel:
                QMessageBox.warning(w, "Update", f"Update gagal diunduh:\n{err}")
            return
        kind, remote = self._pending
        from pathlib import Path
        try:
            if kind == "app":
                selfupdate.install_app_update(Path(path))
                Path(path).unlink(missing_ok=True)
                w.log(f"Update {remote} terpasang — restart…")
                QMessageBox.information(w, "Update", f"Rexxa Translator {remote} terpasang.\nAplikasi akan dibuka ulang.")
                cmd = selfupdate.restart_command()
                QProcess.startDetached(cmd[0], cmd[1:])
            else:
                bat = selfupdate.prepare_full_update(Path(path))
                QMessageBox.information(w, "Update", "Aplikasi akan ditutup, update dipasang, "
                                                     "lalu Rexxa Translator terbuka lagi otomatis.")
                selfupdate.run_detached(bat)
        except Exception as e:
            QMessageBox.warning(w, "Update", f"Update gagal dipasang:\n{e}\n\nVersi lama tetap dipakai.")
            return
        QApplication.quit()
