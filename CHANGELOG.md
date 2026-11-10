# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 1.14.1
- Panel **Properti** kini mengikuti lebar sidebar saat digeser: tidak ada lagi bagian yang terpotong di kanan (font, preset, warna, stroke, jenis balon menyempit dengan rapi).
- Tombol **Posisi** memakai ikon panah yang jelas (kiri, atas, bawah, kanan, kembalikan) dan bisa ditahan untuk menggeser terus. Ikon cocokkan font (tongkat) & ambil warna (pipet) diperbarui.
- Saat belum ada balon dipilih, kolom angka menampilkan nilai netral (Auto, 1.20, 0, 0°), bukan -180° / -10.

## 1.14.0
- **Google Fonts sebagai cadangan pencocokan font**: bila font di aplikasi & perangkat kurang mirip dengan teks asli (SFX, logo judul, tombol ✦), aplikasi mencoba font dari Google Fonts (komik, kuas, tebal, display), memilih yang paling mirip, lalu memasangnya otomatis. Font yang sudah diunduh disimpan & dipakai ulang. Tanpa API key; bila offline, cukup dilewati.
- Pengaturan → Font: tombol **Google Fonts…** untuk mencari & memasang font gratis (kategori komik/kuas, tebal, display, tulisan tangan, atau cari nama).
- Pengaturan → Proses: opsi menyalakan/mematikan pencarian Google Fonts.

## 1.13.0
- **Deteksi warna teks lebih pintar**: warna isi huruf, **garis tepi** (warna + tebal), dan **gradasi** atas→bawah dibaca langsung dari teks asli, lalu dipakai untuk terjemahan. Bekerja untuk huruf merah/emas bergradasi (manhwa), huruf putih bergaris tepi hitam, huruf berwarna bergaris tepi putih, dll. Huruf hitam yang buram tetap dianggap hitam.
- Warna dibaca juga saat **OCR** (termasuk kotak yang dibuat manual dan tombol "OCR ulang").
- Tombol baru **◉** di panel Tipografi: ambil warna dari teks asli untuk balon yang dipilih.
- Pembersihan latar putih lebih bersih: sisa tepi samar huruf berwarna tidak lagi tertinggal.

## 1.12.1
- Logo judul di **latar terang** (mis. judul Korea bergradasi emas-biru): huruf diberi garis tepi gelap agar terbaca, tekstur warna asli tetap dipakai.
- Pencocokan font tidak lagi memilih font simbol / tanpa huruf latin (huruf jadi kotak-kotak); logo judul mengutamakan font tebal.
- Huruf logo bergradasi tidak lagi dianggap "kuas kasar" (efek gores hanya untuk logo yang memang kasar).

## 1.12.0
- **Logo judul seri otomatis**: menu ⚡ (panah di tombol Terjemahkan) → **Logo judul seri di halaman ini…**, isi judul terjemahan sekali (mis. "Player yang Kembali Setelah 10.000 Tahun"). Logo asli dihapus lalu diganti logo terjemahan: kata penting besar, kata sambung kecil, huruf diisi tekstur & warna logo asli, tepi kasar seperti kuas, miring, dan bayangan.
- Setelah judul seri diisi, halaman judul di 3 halaman awal setiap chapter otomatis dikenali & diganti saat ⚡ Terjemahkan.
- Font logo dipilih otomatis yang paling mirip (font aplikasi → font perangkat). Kotak logo bisa digeser/diubah; jenis balon "Logo judul seri" juga bisa dipilih manual.
