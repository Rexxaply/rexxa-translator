# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 1.9.4
- Perbaikan: kotak **ukuran font, jarak baris, jarak huruf, rotasi, dan tebal stroke** di panel Tipografi kini benar-benar menampilkan angkanya (kolom angka baru). Bisa diketik lalu Enter, atau diubah dengan panah ↑/↓ dan roda mouse (Shift = langkah ×10).

## 1.9.3
- Panel **Tipografi**: nilai ukuran font, jarak baris, jarak huruf, dan rotasi kini terlihat. Ukuran otomatis menampilkan angkanya (mis. "Auto · 24"); menaikkan ukuran dari Auto mulai dari angka itu. Jarak baris menampilkan nilai sebenarnya (1.20 = default).

## 1.9.2
- Teks kini benar-benar **di tengah balon**, termasuk balon awan / lonjong (sebelumnya bisa naik ke bagian atas balon).
- Huruf miring dimiringkan **per baris**, jadi teks tetap rata tengah dan hurufnya bisa lebih besar di balon yang sempit.

## 1.9.1
- Teks terjemahan kini **di tengah balon**, di posisi teks aslinya. Huruf miring (italic) tidak lagi keluar dari tepi balon di baris atas/bawah.
- **Teks gradasi**: huruf bergradasi (mis. emas terang ke cokelat di manhwa) dideteksi otomatis dan terjemahannya memakai gradasi yang sama. Bisa diatur manual di panel Tipografi: kotak kedua di sebelah warna teks = warna bawah, tombol × = kembali ke warna polos.

## 1.9.0
- **Narasi tidak lagi raksasa**: teks di pojok panel / di atas langit tidak lagi dianggap balon seukuran panel. Ukuran font otomatis kini mengikuti ukuran huruf aslinya.
- **Balon transparan (manhwa)**: hanya huruf yang dihapus, lalu latar di belakangnya (gradasi, gambar yang tembus) **di-generate ulang**. Tidak ada lagi tempelan warna solid; latar putih hanya diisi bila memang benar-benar polos.
- LaMa kini bekerja per area teks dan hanya mengganti piksel yang dihapus, jadi bagian lain halaman tetap utuh. Garis tepi putih di sekitar huruf narasi ikut dihapus.
- Deteksi lebih lengkap: balon dengan huruf kecil-besar campuran ("A good luck kiss!"), balon pendek ("OH."), baris yang hurufnya menempel ("AS", "OUT"), dan huruf di pita abu-abu balon transparan. SFX Jepang tidak ikut diterjemahkan saat bahasa sumber Inggris.
- Huruf berwarna (mis. emas) diterjemahkan dengan warna yang sama.
