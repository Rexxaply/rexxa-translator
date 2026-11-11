# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z · Jenis update`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

Penomoran MAJOR.MINOR.PATCH:
- **Major update** (X.0.0) — perubahan besar / rombak; bisa ada yang tidak cocok dengan versi lama
- **Minor update** (2.X.0) — fitur baru; proyek & pengaturan lama tetap jalan
- **Patch update** (2.0.X) — perbaikan bug & penyempurnaan kecil tanpa fitur baru

## 2.1.4 · Patch update

- Animasi tombol Simpan: ikon disket berputar (ungu) selama proyek disimpan, minimal 2 putaran, lalu kembali normal

## 2.1.3 · Patch update

- Daftar font menampilkan nama tiap font dengan font itu sendiri (pratinjau langsung, gaya Bold/Italic ikut) — di panel Tipografi & Preset teks
- Daftar pilihan (font, bahasa, preset, dll.) tidak lagi memanjang setinggi layar: maksimal ±14 baris, sisanya digulir

## 2.1.2 · Patch update

- Tema baru mengikuti warna logo: latar biru-gelap yang lembut di mata, aksen ungu-biru, tombol utama bergradasi biru → ungu
- Warna kotak di gambar mengikuti logo: balon biru, teks bebas teal, kotak judul oranye; pesan error & tombol hapus tetap merah lembut
- Font baru: Inter untuk teks & kontrol, Plus Jakarta Sans untuk judul
- Ikon baru: tombol Terjemahkan (文 → A), pen tool (mata pena), dan file proyek .mtproj (logo R)
- Layar awal menampilkan logo baru
- Perbaikan: tombol "Atur kredit & watermark…" sebelumnya tampil sebagai "Atur kredit _watermark…"

## 2.1.1 · Patch update

- Ikon & logo baru Rexxa Translator (jendela aplikasi & layar pembuka). Ikon file .exe ikut berganti saat update penuh / instal baru

## 2.1.0 · Minor update

- Menu Skill baru: Memori cerita — AI mengingat tokoh, gender, panggilan (aku/kamu, gue/lo, kak…) & gaya bicara; disimpan per seri, bisa "Pelajari dari chapter ini (AI)"
- Gaya bahasa terjemahan (santai, gaul, baku, kocak, dramatis) + honorifik dipertahankan / diganti (kak, bang, pak)
- Proofread: cek lokal (belum diterjemahkan, kata dobel, tanda tanya, teks kepanjangan, nama tokoh) + cek AI dengan saran perbaikan
- Kotak judul: buat logo judul dari teks, tempel judul buatan sendiri (Ctrl+V), atau generate dengan AI gambar (API kompatibel OpenAI)
- Export PSD berlapis (Raw · Bersih · tiap balon teks) dan halaman kredit tim + watermark saat export
- Logo judul otomatis lebih rapi: isi huruf gradasi warna logo asli + garis tepi, jumlah baris mengikuti bentuk kotak
