# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 1.10.0
- **Webtoon / strip panjang (manhwa & manhua)**: gambar yang jauh lebih tinggi dari lebarnya (.webp/.jpg/.png) kini terdeteksi dengan benar. Ukuran huruf diukur dari lebar strip, bukan tingginya (sebelumnya teks di strip panjang sama sekali tidak terdeteksi).
- Gambar beresolusi rendah (lebar < 700 px) otomatis diperbesar 2x saat deteksi, jadi teks kecil tetap tertangkap.
- Strip panjang ditampilkan **pas lebar** dan mulai dari atas; tampilan Asli & Hasil tetap bergulir bersamaan.

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
