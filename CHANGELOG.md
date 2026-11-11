# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z · Jenis update`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

Penomoran MAJOR.MINOR.PATCH:
- **Major update** (X.0.0) — perubahan besar / rombak; bisa ada yang tidak cocok dengan versi lama
- **Minor update** (2.X.0) — fitur baru; proyek & pengaturan lama tetap jalan
- **Patch update** (2.0.X) — perbaikan bug & penyempurnaan kecil tanpa fitur baru

## 2.1.0 · Minor update

- Menu Skill baru: Memori cerita — AI mengingat tokoh, gender, panggilan (aku/kamu, gue/lo, kak…) & gaya bicara; disimpan per seri, bisa "Pelajari dari chapter ini (AI)"
- Gaya bahasa terjemahan (santai, gaul, baku, kocak, dramatis) + honorifik dipertahankan / diganti (kak, bang, pak)
- Proofread: cek lokal (belum diterjemahkan, kata dobel, tanda tanya, teks kepanjangan, nama tokoh) + cek AI dengan saran perbaikan
- Kotak judul: buat logo judul dari teks, tempel judul buatan sendiri (Ctrl+V), atau generate dengan AI gambar (API kompatibel OpenAI)
- Export PSD berlapis (Raw · Bersih · tiap balon teks) dan halaman kredit tim + watermark saat export
- Logo judul otomatis lebih rapi: isi huruf gradasi warna logo asli + garis tepi, jumlah baris mengikuti bentuk kotak

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
