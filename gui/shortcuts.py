"""Daftar pintasan keyboard (bisa diubah di Pengaturan → Shortcut).

local=True : hanya aktif saat fokus di gambar / daftar halaman, supaya tidak bentrok
             dengan mengetik di kolom teks (mis. tombol B, F, angka 1–5).
"""

# (id, grup, keterangan, default, local)
SHORTCUTS = [
    ("open", "File", "Buka folder chapter", "Ctrl+O", False),
    ("save", "File", "Simpan proyek", "Ctrl+S", False),
    ("save_as", "File", "Simpan proyek sebagai… (file baru)", "Ctrl+Shift+S", False),
    ("export", "File", "Export As… (pratinjau, PDF / CBZ / ZIP)", "Ctrl+E", False),
    ("settings", "File", "Pengaturan", "Ctrl+,", False),

    ("translate_page", "Proses", "Terjemahkan halaman ini", "F5", False),
    ("translate_all", "Proses", "Terjemahkan semua halaman", "F6", False),
    ("detect_all", "Proses", "Deteksi balon semua halaman", "Shift+F6", False),
    ("render", "Proses", "Render ulang halaman", "Ctrl+R", False),

    ("undo", "Edit", "Undo", "Ctrl+Z", False),
    ("redo", "Edit", "Redo", "Ctrl+Y", False),
    ("redo_alt", "Edit", "Redo (alternatif)", "Ctrl+Shift+Z", False),
    ("box", "Edit", "Tambah kotak teks manual", "B", True),
    ("tool_select", "Alat", "Alat pilih / geser kotak", "V", True),
    ("tool_pen", "Alat", "Pen tool (klik titik-titik, klik titik awal / Enter = selesai)", "P", True),
    ("tool_shape", "Alat", "Shape tool (kotak / oval; tekan lagi = ganti bentuk)", "A", True),
    ("tool_heal", "Alat", "Healing brush (sapukan untuk menghapus, AI membuat ulang latar)", "J", True),
    ("tool_line", "Alat", "Alat garis (seret = garis bebas, Shift = lurus)", "L", True),
    ("tool_patch", "Alat", "Patch tool (lingkari area yang belum rapi -> ditambal area serupa)", "K", True),
    ("brush_up", "Alat", "Perbesar kuas", "]", True),
    ("brush_down", "Alat", "Perkecil kuas", "[", True),
    ("delete", "Edit", "Hapus balon terpilih", "Delete", True),

    ("preset1", "Preset teks", "Terapkan Preset 1", "1", True),
    ("preset2", "Preset teks", "Terapkan Preset 2", "2", True),
    ("preset3", "Preset teks", "Terapkan Preset 3", "3", True),
    ("preset4", "Preset teks", "Terapkan Preset 4", "4", True),
    ("preset5", "Preset teks", "Terapkan Preset 5", "5", True),

    ("next_page", "Tampilan", "Halaman berikutnya", "PgDown", True),
    ("prev_page", "Tampilan", "Halaman sebelumnya", "PgUp", True),
    ("fit", "Tampilan", "Pas layar", "F", True),
]

DEFAULTS = {sid: default for sid, _, _, default, _ in SHORTCUTS}


def current(settings: dict) -> dict:
    """Pintasan yang berlaku: default + yang diubah pengguna."""
    out = dict(DEFAULTS)
    for k, v in (settings.get("shortcuts") or {}).items():
        if k in out and isinstance(v, str):
            out[k] = v
    return out


def conflicts(mapping: dict) -> list[tuple[str, list[str]]]:
    """Pintasan yang dipakai lebih dari satu aksi: [(tombol, [id, ...])]."""
    seen = {}
    for sid, seq in mapping.items():
        if seq:
            seen.setdefault(seq.lower(), []).append(sid)
    return [(k, v) for k, v in seen.items() if len(v) > 1]
