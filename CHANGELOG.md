# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub.

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
