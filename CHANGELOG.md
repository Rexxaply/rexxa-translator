# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z · Jenis update`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

Penomoran MAJOR.MINOR.PATCH:
- **Major update** (X.0.0) — perubahan besar / rombak; bisa ada yang tidak cocok dengan versi lama
- **Minor update** (2.X.0) — fitur baru; proyek & pengaturan lama tetap jalan
- **Patch update** (2.0.X) — perbaikan bug & penyempurnaan kecil tanpa fitur baru

## 3.1.0 · Minor update
- Tab baru GAMBAR di panel kanan: seret & lepas gambar ke halaman, klik untuk pilih dari folder (bisa banyak sekaligus), atau Ctrl+V. Cocok untuk judul chapter, logo, atau kredit.
- Gambar jadi lapisan di halaman: bisa digeser, diubah ukurannya (tarik sudut = rasio tetap, Shift = bebas), diatur opasitasnya, diganti, dan ikut masuk ke hasil, Export, serta PSD. Teks terjemahan tetap bisa ditulis di atasnya.
- Hapus latar (chroma key): Otomatis (termasuk latar kotak-kotak "transparan palsu"), Putih, Hijau, Biru, atau warna pilihan sendiri, dengan pengatur toleransi & halus tepi. Isi gambar yang warnanya sama dengan latar tetap aman. Gambar asli tidak diubah.
- Tombol Gambar (I) di kolom alat langsung membuka tab Gambar.
- Zoom dengan roda mouse kini mengarah ke kursor; tombol + / − di bawah zoom dari tengah tampilan; saat diperkecil halaman berada di tengah.
- Membuka / menutup panel atau mengubah ukuran jendela tidak lagi melompat ke atas halaman, dan zoom yang kamu atur sendiri tidak di-reset.

## 3.0.0 · Major update
- Tampilan baru Liquid Glass: latar gelap bercahaya lembut, panel kaca mengambang, area halaman manga jauh lebih luas.
- Toolbar atas diganti kapsul ringkas: buka/simpan/undo di kiri, bahasa JP → ID dan tombol Terjemahkan (dengan menu pilihan) di kanan.
- Kolom alat di kiri dengan grup ala Photoshop: klik kiri memakai alat, klik kanan memilih isi grup; ikon berganti mengikuti alat yang sedang dipakai.
- Pintasan per grup: Balon (B), Seleksi (A), Perbaikan (J) — tekan Ctrl+Shift+huruf untuk ganti cepat di dalam grup. Pen (P) dan Garis (L) tetap terpisah.
- Balon & seleksi kini bisa kotak atau oval; tahan Shift saat menyeret untuk persegi / lingkaran sempurna.
- Patch digabung ke grup Perbaikan: seret kotak di area lalu pilih cara memperbaikinya.
- Alat Teks baru (T): klik untuk menulis teks bebas di halaman, dengan panel properti sendiri (tidak ikut OCR/terjemah, tetap ada saat deteksi ulang).
- Tahan Ctrl dengan alat apa pun untuk memilih dan memindahkan balon sementara.
- Panel properti berbentuk kartu (Terjemahan, Tipografi, Warna, Balon) yang bisa dibuka/tutup dengan animasi halus; pindah tab juga beranimasi.
- Panel samping bisa disembunyikan dengan Tab, animasi pegas seperti iOS. Tombol layer (H) untuk menampilkan/menyembunyikan kotak balon.
- Kolom garis: mengetik 0 langsung menjadi "-" (tanpa garis).
- Strip halaman di bawah lebih tipis; riwayat proyek maksimal 5, tampil 3 dan sisanya bisa digulir.
- Gulir halus di seluruh aplikasi (per 10 px dengan mouse, 5 px dengan touchpad).
- Jauh lebih ringan: jendela utama terbuka ±9× lebih cepat, proyek besar ±3–5× lebih cepat (thumbnail dimuat di latar), Pengaturan ±3× lebih cepat, daftar font disimpan.

## 2.5.1 · Patch update
- Kotak font: klik kotaknya langsung menampilkan daftar semua font (font yang dipakai sudah terpilih di tengah daftar), tanpa harus mengetik dulu.
- Saat daftar terbuka, nama font lama terseleksi: huruf pertama yang diketik langsung menggantikannya dan menyaring daftar.

## 2.5.0 · Minor update
- Cari font di panel properti: ketik di kotak font, daftar langsung tersaring di setiap huruf (nama boleh cocok di bagian mana saja, bisa beberapa kata).
- Bagian nama yang cocok disorot; font yang diawali ketikan tampil paling atas.
- Pilih dengan klik atau ↑/↓ + Enter; Enter langsung memakai hasil teratas. Daftar lengkap tetap bisa dibuka lewat panah.

## 2.4.0 · Minor update
- Render langsung: hasil terjemahan berubah di setiap ketikan, tanpa menunggu dan tanpa tampilan berkedip.
- Mengubah warna, ukuran, font, perataan, posisi teks, serta undo/redo juga langsung terlihat.
- Menggeser / mengubah ukuran kotak balon: teks asli di posisi lama kembali, area baru langsung dihapus dan teks ikut pindah. Setelah kotak dilepas, area itu dihapus ulang dengan kualitas penuh.
- Hasil, thumbnail, dan proyek disimpan otomatis setelah berhenti menyunting sejenak.
