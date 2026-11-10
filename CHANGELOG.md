# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

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

## 1.7.1
- Teks kini mengikuti **bentuk asli balon** dan ukurannya menyesuaikan balon (lebih besar, tidak lagi kekecilan); posisinya di bagian terdalam balon, jadi ekor balon tidak menggeser teks.
- Jarak baris default **1.2** seperti lettering manga (bisa diatur di Pengaturan → Teks); kata pendek tidak lagi dipotong-potong (mis. "KATSUKI- / SAN!").
- Panel **Tipografi** dirapikan: ukuran + preset 1–5, B / I / AA / Aa / aa + rata, jarak baris, jarak huruf, rotasi, tombol geser posisi, warna teks & stroke.

## 1.7.0
- **Hemat token**: prompt LLM lebih ringkas, teks berupa tanda baca dan teks kembar tidak dikirim, glosarium hanya istilah yang dipakai, dan terjemahan disimpan di cache sehingga teks yang sama tidak diterjemahkan ulang. Jumlah token tampil di tab LOG.
- Pengaturan → **Teks**: Preset 1–5 (font, tebal, miring, KAPITAL/kecil), ukuran font default (Auto-Fit/angka), penamaan file export. Tombol 1–5 di panel Tipografi menerapkan preset ke balon.
- Pengaturan → **Shortcut**: lihat & ubah semua pintasan keyboard.
- Pengaturan → **Data**: ukuran & hapus cache terjemahan, cache gambar, model AI; reset shortcut; reset aplikasi.
