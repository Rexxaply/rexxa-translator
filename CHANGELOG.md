# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 2.0.6

- Deteksi teks lebih kuat: balon kecil ("HUH?") tidak lagi tergabung dengan garis wajah/rambut
- Satu huruf + titik-titik ("I...", "A...") sekarang terdeteksi & terbaca benar
- Tulisan tangan tipis huruf kecil di latar terang ("Is that it...") tidak lagi terlewat
- OCR: titik-titik di ujung baris ikut terbaca ("TALK..." bukan "TALK."), spasi setelah "..." tidak hilang

## 2.0.5

- Hapus teks lebih rapi di latar raster/berbintik: bekas teks diisi tekstur aslinya (tanpa gumpalan putih / tambalan terang)
- Teks bergaris tepi putih (mis. di atas tembok) dihapus bersih beserta tepinya; terjemahan ikut diberi garis tepi putih
- Garis kotak narasi & tepi balon tidak lagi ikut terhapus / tercoret
- Patch Tool: perapian otomatis area yang kurang mulus + alat Patch manual (K) seperti di Photoshop
- Sambung otomatis tepi balon yang terputus saat teks dihapus (garis objek seperti tembok/rambut dibiarkan)
- Font hiasan aneh (Goudy Stout, Algerian, dll.) tidak dipakai lagi untuk dialog & narasi

## 2.0.4

- Edit teks jauh lebih cepat (±3×): hanya balon yang diubah yang dihitung & digambar ulang, geser teks langsung tampil
- Hasil render langsung tampil dari memori (tanpa membaca ulang file), jeda render otomatis lebih singkat
- Scan balon lebih cepat (±35%) dengan hasil yang sama persis
- OCR lebih cepat & akurat: baca per baris memakai posisi baris dari deteksi (tanpa tahap deteksi teks yang berat), hasil OCR disimpan agar tidak dibaca dua kali
- OCR lebih pintar: memilih hasil baca terbaik (kamus + jumlah huruf), varian bersih-bintik, menyambung kata ber-tanda hubung ("FOL- LOWING"), kapital seragam, I'M / I'VE
- Hapus teks di halaman webtoon panjang lebih hemat memori
- Mode hemat: memori sementara lebih kecil; batas thread juga berlaku saat edit & render

## 2.0.3
- **Hapus teks 4 tahap (lebih rapi)**: (1) mask dibuat hanya dari bentuk huruf yang terbaca -- bintik raster / butiran kertas tidak ikut; (2) bekas teks diisi sesuai latarnya: warna polos, butiran balon bertekstur, "pulau putih" di belakang teks tetap putih, sisanya dibuat ulang AI (LaMa); (3) garis balon / bingkai narasi / arsiran yang ikut terpotong dikembalikan dari gambar asli; (4) sisa huruf & sambungan dirapikan lagi oleh AI.
- Balon putih berbintik tidak lagi meninggalkan tambalan abu-abu buram.
- Deteksi: baris pendek di bawah teks ("DAMN / IT...") ikut terbaca & terhapus.
- Teks tidak lagi keluar dari kotak narasi yang sempit.
- Perbaikan bug: halaman kosong setelah menambah / menghapus halaman; kotak manual buatan sendiri tidak lagi ikut terbuang oleh filter OCR; koreksi OCR tidak lagi mengubah logat yang disengaja ("BESHT").

## 2.0.2
- **Terjemahkan Semua lebih cepat, tetap ramah 4 CPU**:
  - Dua tahap berjalan bersamaan: halaman berikutnya dideteksi & di-OCR sementara halaman ini diterjemahkan & dirender (waktu tunggu jaringan tidak lagi membuat CPU menganggur).
  - OCR hanya membaca ulang (versi diluruskan / huruf berongga) bila hasil pertama benar-benar ragu.
  - Google Translate mengirim beberapa teks sekaligus (maks. 4), bukan satu per satu.
  - Gambar halaman disimpan sebentar di memori, tidak dibuka ulang dari disk berkali-kali.
  - 1 inti CPU selalu dibiarkan bebas untuk tampilan aplikasi; antrean maks. 1 halaman supaya memori tetap kecil.
- Mode Hemat kini otomatis hanya untuk RAM < 6 GB atau CPU 2 inti (bisa dipaksa di Pengaturan → Proses → Performa).
