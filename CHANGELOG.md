# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 1.6.5
- Changelog di jendela update kini hanya menampilkan 5 versi terbaru.

## 1.6.4
- Teks **putih bergaris tepi hitam di atas gambar** (narasi/caption, mis. "IT HAPPENED A FEW DAYS AGO..") kini bisa diterjemahkan lewat kotak manual (**B**): huruf beserta garis tepinya terhapus bersih, dan terjemahannya otomatis **putih dengan stroke hitam**.

## 1.6.3
- Perbaikan error **"'NoneType' object has no attribute 'write'"** saat OCR pertama kali dipakai di versi .exe (progres unduhan model kini dicatat ke `%APPDATA%\RexxaTranslator\rexxa.log`).

## 1.6.2
- Deteksi: balon yang **menyatu tanpa garis pemisah** (mis. "RIGHT..." + "SOMETHING LIKE THIS") kini dibelah tepat di bagian yang menyempit, jadi tiap balon dideteksi, di-OCR, dan diterjemahkan sendiri-sendiri.
- OCR hanya membaca teks di dalam balonnya sendiri (tidak ikut membaca balon tetangga), tanda baca kecil seperti "..." tetap terbaca.
- Deteksi jauh lebih cepat di halaman dengan banyak screentone.

## 1.6.1
- Tab **Font** baru di Pengaturan: instal font sendiri (.ttf/.otf/.ttc) lewat tombol atau seret file, pratinjau, jadikan default, hapus.
- Font yang diinstal disimpan di folder data pribadi, jadi tetap ada walau aplikasi di-update.
- Wild Words / Anime Ace yang diinstal lewat aplikasi otomatis diutamakan.
