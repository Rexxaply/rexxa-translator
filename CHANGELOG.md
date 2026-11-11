# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z · Jenis update`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

Penomoran MAJOR.MINOR.PATCH:
- **Major update** (X.0.0) — perubahan besar / rombak; bisa ada yang tidak cocok dengan versi lama
- **Minor update** (2.X.0) — fitur baru; proyek & pengaturan lama tetap jalan
- **Patch update** (2.0.X) — perbaikan bug & penyempurnaan kecil tanpa fitur baru

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

## 2.3.1 · Patch update

- Perbaikan: jendela Pengaturan & kotak pesan tidak lagi berkedip saat dibuka (muncul langsung dengan animasi pop-up)
- Semua dropdown & menu bergaya Liquid Glass: kaca frosted (isi aplikasi di belakang tampak buram), sudut membulat, pilihan berbentuk pil, muncul halus

## 2.3.0 · Minor update

- Pengaturan baru bergaya Liquid Glass: menu samping, isi dikelompokkan rapi, catatan kegunaan saat kursor diarahkan ke setiap pengaturan, konfirmasi Simpan / Kembali / Tutup tanpa simpan
- Preset engine: simpan beberapa pengaturan engine (awal "Default"), ganti nama, hapus, dan pindah cepat dari menu panah tombol Terjemahkan saat satu model gangguan
- Semua kotak pesan bergaya Liquid Glass: kaca frosted (isi aplikasi di belakang tampak buram), lencana ikon sesuai jenis pesan, animasi pop-up masuk & keluar
- Folder chapter tetap bersih: hasil kerja disimpan di folder tersembunyi aplikasi; gambar keluar lewat Export → "Gambar (ke folder)"
- Hasil kerja per chapter bisa dihapus di Pengaturan → Data, dan otomatis dibersihkan bila tidak dibuka > 30 hari (bisa diatur)
- Geser teks balon dengan tombol panah keyboard (Shift = 10 px)
- Edit teks ±2,5× lebih cepat: hasil langsung tampil, file disimpan di belakang layar
- Animasi tombol Simpan lebih santai & mulus ala iOS
