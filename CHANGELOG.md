# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub.

## 1.6.4
- Teks **putih bergaris tepi hitam di atas gambar** (narasi/caption, mis. "IT HAPPENED A FEW DAYS AGO..") kini bisa diterjemahkan lewat kotak manual (**B**): huruf beserta garis tepinya terhapus bersih, dan terjemahannya otomatis **putih dengan stroke hitam**.

## 1.6.3
- Perbaikan error **"'NoneType' object has no attribute 'write'"** saat OCR pertama kali dipakai di versi .exe (progres unduhan model kini dicatat ke `%APPDATA%\RexxaTranslator\rexxa.log`).

## 1.6.2
- Deteksi: balon yang **menyatu tanpa garis pemisah** (mis. "RIGHT..." + "SOMETHING LIKE THIS") kini dibelah tepat di bagian yang menyempit, jadi tiap balon dideteksi, di-OCR, dan diterjemahkan sendiri-sendiri.
- OCR hanya membaca teks di dalam balonnya sendiri (tidak ikut membaca balon tetangga), tanda baca kecil seperti "..." tetap terbaca.
- Deteksi jauh lebih cepat di halaman dengan banyak screentone.

## 1.6.1
- Tab **Font** baru di Pengaturan: instal font sendiri (.ttf/.otf/.ttc) lewat tombol atau seret file, pratinjau, jadikan default, hapus.
- Font yang diinstal disimpan di folder data pribadi, jadi tetap ada walau aplikasi di-update.
- Wild Words / Anime Ace yang diinstal lewat aplikasi otomatis diutamakan.

## 1.6.0
- Undo **Ctrl+Z** dan redo **Ctrl+Y** (juga tombol di toolbar): geser/ubah ukuran kotak, tambah/hapus balon, edit teks & gaya, hasil proses.
- Gambar HASIL kini bisa diklik: balon bisa dipilih dan digeser dari sisi kiri maupun kanan.
- Kotak balon bisa digeser bebas dan diubah ukurannya dari ke-4 sisi dan ke-4 sudut.
- Kursor panah biasa; berubah jadi ikon geser di atas kotak. Layar tetap bisa digeser dengan menyeret area kosong.
- Gambar ASLI dan HASIL selalu sama besar dan sejajar.

## 1.5.1
- Jendela update kini menampilkan changelog lengkap dari versi terpasang sampai versi terbaru.

## 1.5.0
- Deteksi: dua balon yang saling menempel (mis. "RIGHT..." | "SOMETHING LIKE THIS") kini terpisah jadi dua balon.
- Gaya huruf ala scanlation: HURUF KAPITAL + miring, font komik otomatis (Wild Words / Anime Ace bila terpasang di Windows, selain itu Comic Neue yang kini ikut dibundel).
- Teks mengikuti bentuk oval balon, kata tidak lagi dipotong-potong (hanya dipisah di tanda hubung yang memang ada, mis. "KATSUKI-" / "SAN!").
- Tombol miring (I) per balon di panel Tipografi.
- Tanda baca kecil di dekat garis balon (mis. "-") ikut terhapus.

## 1.4.1
- Update sepenuhnya otomatis: tidak perlu mengisi sumber update lagi (tab Update di Pengaturan diganti tab Tentang).
- Update dicek setiap kali aplikasi dibuka.

## 1.4.0
- Update otomatis dari GitHub: klik **Update sekarang**, aplikasi mengunduh, memasang, lalu membuka ulang sendiri.
- Update rutin kini kecil & cepat (hanya kode aplikasi); mesin (.exe, PyTorch, OCR) hanya diunduh ulang bila berubah.
- Jika update gagal dibuka, aplikasi otomatis kembali ke versi sebelumnya.
- Rilis .exe dibuat otomatis oleh GitHub Actions.

## 1.3.2
- Pilihan bahasa terakhir diingat.
- Peringatan bila bahasa asal salah pilih (mis. komik Inggris diset Japanese).

## 1.3.1
- Gambar asli & hasil selalu tampil berdampingan; halaman yang sudah diterjemahkan dirender otomatis.

## 1.3.0
- Tampilan baru: toolbar ikon, thumbnail halaman, Asli | Terjemahan berdampingan, panel properti.
- Hasil diperbarui otomatis saat mengedit teks/gaya.

## 1.2.1
- Perbaikan error `torchvision::nms`; OCR gagal tidak lagi ditempel ke gambar.

## 1.2.0
- Detektor balon baru (cari teks dulu, lalu balonnya); typesetting tidak memotong kata.
