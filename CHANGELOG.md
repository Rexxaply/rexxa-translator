# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 1.21.0
- **Layar awal baru**: saat aplikasi dibuka tanpa gambar, tampil layar "Buka gambar untuk mulai". Seret & lepas file/folder ke area itu, tekan Ctrl+O, atau klik tombol **Buka folder chapter / Buka gambar / Buka proyek**. Panel halaman & properti baru muncul setelah ada gambar.
- **Deteksi balon SEMUA halaman** (menu ⚡, Shift+F6): mendeteksi kotak teks di seluruh chapter sekaligus tanpa OCR/terjemah, jadi kotak bisa dicek dulu. Bila sebagian halaman sudah punya balon, pilih "Hanya yang belum" atau "Deteksi ulang semua".
- Nama default proyek baru kini **untitled.mtproj**.
- Ikon folder (buka/simpan) di toolbar selalu aktif.

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
