# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 2.0.2
- **Terjemahkan Semua lebih cepat, tetap ramah 4 CPU**:
  - Dua tahap berjalan bersamaan: halaman berikutnya dideteksi & di-OCR sementara halaman ini diterjemahkan & dirender (waktu tunggu jaringan tidak lagi membuat CPU menganggur).
  - OCR hanya membaca ulang (versi diluruskan / huruf berongga) bila hasil pertama benar-benar ragu.
  - Google Translate mengirim beberapa teks sekaligus (maks. 4), bukan satu per satu.
  - Gambar halaman disimpan sebentar di memori, tidak dibuka ulang dari disk berkali-kali.
  - 1 inti CPU selalu dibiarkan bebas untuk tampilan aplikasi; antrean maks. 1 halaman supaya memori tetap kecil.
- Mode Hemat kini otomatis hanya untuk RAM < 6 GB atau CPU 2 inti (bisa dipaksa di Pengaturan → Proses → Performa).

## 2.0.1
- **Font otomatis untuk semua teks + memori font**: dialog, dialog miring, dialog tebal, narasi, dan narasi huruf kecil masing-masing dicarikan font yang paling mirip dengan teks aslinya, lalu **diingat di proyek** sehingga halaman berikutnya langsung memakai font yang sama (cepat & konsisten se-chapter). Font yang kamu pilih manual juga diingat. Menu ⚡ → "Lupakan font yang diingat proyek ini" untuk mencocokkan ulang.
- **Lebih ringan untuk PC spesifikasi rendah** (Pengaturan → Proses → Performa: Otomatis / Hemat / Normal): memori dibersihkan setiap halaman, thread dibatasi supaya aplikasi tetap responsif, AI hapus teks memakai potongan lebih kecil, jeda otomatis saat RAM hampir habis, halaman diulang dengan cara ringan bila memori penuh, dan **simpan otomatis setiap 5 halaman** saat Terjemahkan Semua.
- **Deteksi lebih lengkap**: narasi kecil di panel berarsir/gelap ("I feel chilly..."), teks di balon ledakan bergerigi ("FORSINA!?"), dan seruan pendek ("WH...") kini ikut terdeteksi. Kotak balon yang terpotong diperluas sampai seluruh teks asli.
- **Hasil OCR lebih bersih**: kotak yang ternyata rambut / raster dibuang (dicek dengan kamus), sisa garis balon ("|", "[") dihapus, apostrof hilang dibetulkan (TLL → I'LL, DONT → DON'T).
- **Tampilan hasil lebih rapi**: ukuran huruf diseragamkan antar balon, narasi huruf kecil tidak lagi dipaksa kapital, teks gelap di latar gelap otomatis diberi garis tepi putih, ekor huruf & tanda baca di ujung ikut terhapus.

## 2.0.0
- **Kelola halaman**:
  - Tombol **+** di samping "HALAMAN" untuk menambah gambar baru ke proyek.
  - **Tahan & seret** halaman di daftar untuk mengubah urutannya sesuka hati.
  - **Klik kanan** halaman: tambah gambar di akhir, sisipkan gambar setelah halaman ini, pindah ke atas/bawah, dan **hapus halaman** (bisa beberapa sekaligus dengan Ctrl/Shift + klik, atau tombol Delete). File gambarnya tidak ikut terhapus dari komputer.
- **Riwayat proyek di layar awal** kini berupa daftar menurun: yang **terakhir dibuka di paling atas**, yang lama turun ke bawah (3 teratas tampil, 10 tersimpan di menu ikon folder).
- Setiap proyek menampilkan **kapan terakhir dibuka**: "2 menit yang lalu", "4 jam 39 menit yang lalu", "2 hari yang lalu", dan seterusnya. Diperbarui otomatis; waktunya juga tampil di menu "Proyek terakhir".
- **Tata letak teks lebih rapi**: kata dibagi ulang supaya setiap baris mengisi ruang balon secara seimbang (baris tengah lebih panjang di balon oval), tanpa baris yatim, dan memotong kata dengan tanda hubung buatan hanya bila benar-benar terpaksa. Kata ber-tanda-hubung asli (mis. "DASAR-DASARMU") boleh dipisah di tanda hubungnya.
- Teks bebas yang terbaca sebagai sampah oleh OCR (mis. SFX Jepang di komik Inggris) tidak ikut diterjemahkan dan ditempel.

## 1.26.0
- **Kembali ke layar awal**: menu ikon folder → "Kembali ke layar awal" menutup proyek yang sedang dibuka (ditanya simpan dulu bila ada perubahan) dan menampilkan layar awal lagi.
- **Riwayat proyek di menu ikon folder**: submenu **"Proyek terakhir"** berisi 10 proyek terbaru; klik untuk membuka (ditanya simpan dulu bila proyek sekarang belum disimpan). Ada juga "Hapus riwayat".
- Layar awal kini menampilkan **3 proyek terbaru** saja (berjajar di layar lebar). Tombol "Hapus riwayat" di layar awal sekarang berfungsi.

## 1.25.0
- **Proyek terakhir di layar awal**: 5 proyek .mtproj terbaru (yang pernah dibuka / disimpan) tampil di bawah tombol "Buka", lengkap dengan nama, folder, dan waktu terakhir diubah. Klik untuk langsung membuka; tombol × menghapusnya dari daftar (file proyeknya tidak dihapus). Proyek yang filenya sudah tidak ada otomatis disembunyikan.
