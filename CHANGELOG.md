# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 1.20.0
- **Ikon file proyek**: file **.mtproj** kini punya ikon Rexxa Translator di Windows Explorer dan bisa dibuka dengan **klik ganda** (didaftarkan otomatis saat aplikasi dibuka, tanpa hak admin).
- **Simpan sebagai…** (Ctrl+Shift+S, di menu ikon folder): simpan proyek ke file baru, mis. untuk membuat cadangan / versi lain. File lama tetap seperti terakhir disimpan.

## 1.19.0
- **Tampilan alert baru** untuk semua pesan aplikasi (simpan, error, peringatan, konfirmasi, update, data, font): kartu gelap membulat, lencana ikon berwarna sesuai jenis pesan, judul tebal di tengah, keterangan redup, dan tombol selebar sama (utama merah muda, bahaya merah lembut, biasa abu-abu).
- Pesan keluar aplikasi: **"Simpan perubahan sebelum menutup?"** dengan tombol **Simpan .mtproj / Jangan simpan / Batal**.

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
