# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 1.9.1
- Teks terjemahan kini **di tengah balon**, di posisi teks aslinya. Huruf miring (italic) tidak lagi keluar dari tepi balon di baris atas/bawah.
- **Teks gradasi**: huruf bergradasi (mis. emas terang ke cokelat di manhwa) dideteksi otomatis dan terjemahannya memakai gradasi yang sama. Bisa diatur manual di panel Tipografi: kotak kedua di sebelah warna teks = warna bawah, tombol × = kembali ke warna polos.

## 1.9.0
- **Narasi tidak lagi raksasa**: teks di pojok panel / di atas langit tidak lagi dianggap balon seukuran panel. Ukuran font otomatis kini mengikuti ukuran huruf aslinya.
- **Balon transparan (manhwa)**: hanya huruf yang dihapus, lalu latar di belakangnya (gradasi, gambar yang tembus) **di-generate ulang**. Tidak ada lagi tempelan warna solid; latar putih hanya diisi bila memang benar-benar polos.
- LaMa kini bekerja per area teks dan hanya mengganti piksel yang dihapus, jadi bagian lain halaman tetap utuh. Garis tepi putih di sekitar huruf narasi ikut dihapus.
- Deteksi lebih lengkap: balon dengan huruf kecil-besar campuran ("A good luck kiss!"), balon pendek ("OH."), baris yang hurufnya menempel ("AS", "OUT"), dan huruf di pita abu-abu balon transparan. SFX Jepang tidak ikut diterjemahkan saat bahasa sumber Inggris.
- Huruf berwarna (mis. emas) diterjemahkan dengan warna yang sama.

## 1.8.0
- **Hapus teks lebih rapi**: kini hanya **huruf** yang dideteksi & dihapus (bukan garis balon, rambut, atau gambar di sekitarnya), lalu bekasnya diisi warna latar (latar polos) atau **di-generate ulang oleh AI** LaMa (latar bergambar). Balon tidak lagi terpotong atau tertutup kotak putih.
- Terjemahan teks bebas / balon terbuka ditempel di **area putih balon** (boleh lebih luas dari kotaknya), tidak lagi keluar dari balon.
- Kata panjang dipenggal di **batas suku kata** (mis. KEBERUN-TUNGAN).

## 1.7.3
- Sidebar lebih ramping (HALAMAN ±128 px, PROPERTI ±240 px) supaya fokus ke halaman manga; isi panel dipadatkan, kotak warna jadi kotak kecil (kode warna muncul saat disorot).

## 1.7.2
- Perbaikan: aplikasi 1.7.1 gagal dibuka ("QVBoxLayout already deleted").
- Bila sebuah update membuat jendela gagal dibuka, aplikasi kini otomatis kembali ke versi sebelumnya.
- Setiap rilis kini diuji dengan benar-benar membuat jendela utama sebelum diterbitkan.
