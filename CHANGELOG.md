# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z · Jenis update`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

Penomoran MAJOR.MINOR.PATCH:
- **Major update** (X.0.0) — perubahan besar / rombak; bisa ada yang tidak cocok dengan versi lama
- **Minor update** (2.X.0) — fitur baru; proyek & pengaturan lama tetap jalan
- **Patch update** (2.0.X) — perbaikan bug & penyempurnaan kecil tanpa fitur baru

## 2.0.8 · Patch update

- Jenis update kini tertulis jelas: Major / Minor / Patch update (badge berwarna di jendela "Update tersedia", juga di catatan rilis & changelog)

## 2.0.7 · Patch update

- Export As… (Ctrl+E): dialog seperti print — pratinjau dulu, pilih halaman saat ini / semua / rentang (mis. 1-5, 8)
- PDF Manga (1 gambar = 1 halaman) atau Manhwa / Manhua (strip disambung, dipotong di celah antar panel)
- CBZ + ComicInfo.xml (judul, chapter, penerjemah, genre, arah baca) untuk Mihon, Komga, Kavita, dll.
- Paket Local Source Mihon: folder seri + cover + info, tinggal ekstrak ke Mihon/local/
- Pilihan format gambar (Asli / JPG / WebP) & kualitas; halaman yang belum diterjemahkan bisa disertakan pakai gambar asli

## 2.0.6 · Patch update

- Deteksi teks lebih kuat: balon kecil ("HUH?") tidak lagi tergabung dengan garis wajah/rambut
- Satu huruf + titik-titik ("I...", "A...") sekarang terdeteksi & terbaca benar
- Tulisan tangan tipis huruf kecil di latar terang ("Is that it...") tidak lagi terlewat
- OCR: titik-titik di ujung baris ikut terbaca ("TALK..." bukan "TALK."), spasi setelah "..." tidak hilang

## 2.0.5 · Patch update

- Hapus teks lebih rapi di latar raster/berbintik: bekas teks diisi tekstur aslinya (tanpa gumpalan putih / tambalan terang)
- Teks bergaris tepi putih (mis. di atas tembok) dihapus bersih beserta tepinya; terjemahan ikut diberi garis tepi putih
- Garis kotak narasi & tepi balon tidak lagi ikut terhapus / tercoret
- Patch Tool: perapian otomatis area yang kurang mulus + alat Patch manual (K) seperti di Photoshop
- Sambung otomatis tepi balon yang terputus saat teks dihapus (garis objek seperti tembok/rambut dibiarkan)
- Font hiasan aneh (Goudy Stout, Algerian, dll.) tidak dipakai lagi untuk dialog & narasi

## 2.0.4 · Patch update

- Edit teks jauh lebih cepat (±3×): hanya balon yang diubah yang dihitung & digambar ulang, geser teks langsung tampil
- Hasil render langsung tampil dari memori (tanpa membaca ulang file), jeda render otomatis lebih singkat
- Scan balon lebih cepat (±35%) dengan hasil yang sama persis
- OCR lebih cepat & akurat: baca per baris memakai posisi baris dari deteksi (tanpa tahap deteksi teks yang berat), hasil OCR disimpan agar tidak dibaca dua kali
- OCR lebih pintar: memilih hasil baca terbaik (kamus + jumlah huruf), varian bersih-bintik, menyambung kata ber-tanda hubung ("FOL- LOWING"), kapital seragam, I'M / I'VE
- Hapus teks di halaman webtoon panjang lebih hemat memori
- Mode hemat: memori sementara lebih kecil; batas thread juga berlaku saat edit & render
