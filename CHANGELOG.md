# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 1.16.1
- **Memperbarui hasil tetap cepat setelah membuka proyek tersimpan**: hasil bersih yang tersimpan langsung dipakai, dan saat balon digeser / diubah / ditambah / dihapus / di-undo, hanya area balon itu yang dibersihkan ulang (bukan seluruh halaman).
- Model AI hapus teks (LaMa) dimuat di latar belakang begitu proyek / gambar dibuka, jadi proses pertama tidak lagi menunggu model dimuat.

## 1.16.0
- **Pengaturan gradasi seperti Photoshop**: tombol gradasi baru di panel Tipografi (di sebelah warna teks) membuka pengaturan:
  - **Bentuk**: Linear, Cermin (reflected), Oval (radial), **Pisah 2 warna** (batas tegas).
  - **Arah**: 8 tombol arah cepat (↓ → ↘ dst.) atau putar kenop untuk sudut bebas 0–359°.
  - **Posisi**: seberapa jauh warna pertama sebelum berganti (mis. pisah di 30%).
  - **Kehalusan**: dari batas tegas sampai peralihan halus penuh.
  - **Ulangi tiap baris** atau satu gradasi untuk seluruh teks; tukar warna; reset; hapus gradasi.
  - Perubahan langsung terlihat di hasil, bisa di-undo.

## 1.15.0
- **Export PDF semua halaman** (menu Export → Export PDF):
  - **Otomatis**: aplikasi mengenali sendiri manga (halaman pendek) atau manhwa/manhua (strip panjang).
  - **Manga**: 1 gambar = 1 halaman PDF, ukuran sesuai gambar.
  - **Manhwa / Manhua**: semua halaman disambung jadi satu strip panjang (lebar disamakan), lalu dibagi ke halaman PDF setinggi mungkin; potongan dicari di celah polos antar panel supaya panel tidak terbelah.

## 1.14.3
- **Memperbarui hasil jauh lebih cepat**, terutama untuk strip webtoon panjang: hapus teks ±7x lebih cepat (hanya mengolah area di sekitar tiap balon, bukan seluruh halaman), menyusun teks ±2,5x lebih cepat (ukuran kata disimpan di cache), dan file sementara disimpan dengan kompresi ringan.

## 1.14.2
- Perbaikan warna: tepi huruf yang sedikit lebih gelap (efek JPEG / penajaman gambar) tidak lagi dikira **garis tepi hitam tebal**. Garis tepi hanya dipakai bila benar-benar kontras dengan isi huruf (mis. putih/hitam, kuning/merah tua).
- Tanda baca yang tidak dimiliki font (mis. tanda pisah panjang "—", "…", tanda kutip miring) tidak lagi tampil sebagai kotak kosong; otomatis diganti versi biasanya ("-", "...", '"').
