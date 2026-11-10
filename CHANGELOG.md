# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 1.18.1
- Tombol yang tidak bisa ditekan kini benar-benar **redup** (ikonnya ikut gelap), bukan hanya tidak bisa diklik: Simpan, Undo, Redo, alat sunting, halaman sebelumnya/berikutnya, Export, dan ukuran kuas (aktif hanya saat Healing brush dipilih). Sebelum ada gambar yang dibuka, alat-alat yang butuh halaman juga redup.

## 1.18.0
- Tombol **Simpan** kini hanya aktif bila ada perubahan yang belum disimpan (ikon baru, dengan titik merah saat ada perubahan; judul jendela diberi tanda •).
- Menutup aplikasi dengan perubahan yang belum disimpan memunculkan pertanyaan **Simpan / Jangan simpan / Batal**. Nama default proyek baru: **unfiledfiles.mtproj**. Hal yang sama juga ditanyakan sebelum aplikasi dibuka ulang untuk update.
- **Undo** dibatasi **5 langkah** per halaman, **Redo** memuat langkah yang di-undo. Tombol Undo / Redo otomatis nonaktif saat sudah mentok.

## 1.17.0
- **Alat sunting gambar** di toolbar (bisa dipakai di gambar Asli maupun Hasil):
  - **Pen tool (P)**: klik titik-titik mengelilingi area; klik titik awal / klik kanan / Enter = selesai, Backspace = hapus titik terakhir, Esc = batal.
  - **Shape tool (A)**: seret kotak atau oval (tekan A lagi untuk ganti bentuk, Shift = persegi/lingkaran).
  - Setelah area dibuat, pilih: **Hapus dengan AI (LaMa)** (latar dibuat ulang), isi putih, isi warna, isi warna latar sekitar, kembalikan gambar asli, buat kotak teks, atau jadikan bentuk balon terpilih.
  - **Healing brush (J)**: sapukan di atas noda / sisa teks / objek, AI LaMa membuat ulang latarnya. Ukuran kuas di toolbar atau tombol **[ ]**.
  - **V** = kembali ke alat pilih. Semua suntingan tersimpan di proyek dan bisa di-undo (Ctrl+Z).
- Perbaikan: hasil bersih proyek tersimpan kini benar-benar langsung dipakai saat proyek dibuka (perbaikan 1.16.1 belum aktif).

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
