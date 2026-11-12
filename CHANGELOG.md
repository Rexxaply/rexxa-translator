# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z · Jenis update`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

Penomoran MAJOR.MINOR.PATCH:
- **Major update** (X.0.0) — perubahan besar / rombak; bisa ada yang tidak cocok dengan versi lama
- **Minor update** (2.X.0) — fitur baru; proyek & pengaturan lama tetap jalan
- **Patch update** (2.0.X) — perbaikan bug & penyempurnaan kecil tanpa fitur baru

## 2.3.6 · Patch update
- Membuka Pengaturan: tidak ada lagi jendela kecil berbar judul "Rexxa Translator" yang muncul sesaat sebelum pop-up.
- Animasi pop-up tidak lagi tertahan di panel kaca kosong lalu meloncat; kalau PC sempat tersendat, animasi berhenti sejenak lalu lanjut mulus.
- Animasi pop-up lebih ringan: jendela utama tidak lagi digambar ulang di setiap frame.

## 2.3.5 · Patch update
- Dropdown & menu di Windows: tidak ada lagi warna hitam di pojok lengkungan (popup kini benar-benar transparan).
- Pop-up Pengaturan & dialog lain: kaca dan isinya muncul bersamaan sejak frame pertama, tanpa panel kaca kosong yang terlihat seperti glitch.

## 2.3.4 · Patch update

- Perbaikan: tidak ada lagi lapisan kaca setengah transparan ("hantu") sebelum Pengaturan & kotak pesan muncul — kaca langsung pekat lalu mengembang, isi menyusul; saat ditutup kaca mengecil lalu lenyap
- Perbaikan: dropdown & menu tidak lagi punya pojok hitam di lengkungannya

## 2.3.3 · Patch update

- Perbaikan: dropdown & menu tidak lagi menjalankan animasi ganda (efek bawaan Windows dimatikan untuk aplikasi ini)
- Perbaikan: tidak ada lagi garis buram sekilas sebelum pop-up Pengaturan muncul
- Perbaikan: tidak ada bayangan ganda saat Pengaturan & kotak pesan dibuka / ditutup (kaca muncul dulu, lalu isinya; saat tutup isinya hilang dulu)
- Dropdown tidak lagi tembus pandang saat muncul; kaca frosted lebih lembut

## 2.3.2 · Patch update

- Perbaikan: glitch saat membuka Pengaturan & kotak pesan (batang gulir yang tiba-tiba muncul di akhir animasi, animasi bawaan Windows yang bertabrakan)
- Keterangan pengaturan kini hanya muncul saat kursor diarahkan ke ikon (i)
