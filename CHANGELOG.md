# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 1.6.7
- Layar ASLI dan TERJEMAHAN kini selalu sama lebar (dibagi rata 50:50).

## 1.6.6
- Perbaikan: teks di balon kata kembali terhapus bersih (di 1.6.4–1.6.5 sebagian huruf, mis. "Katsuki-san!", tertinggal dan tertumpuk dengan terjemahan).

## 1.6.5
- Changelog di jendela update kini hanya menampilkan 5 versi terbaru.

## 1.6.4
- Teks **putih bergaris tepi hitam di atas gambar** (narasi/caption, mis. "IT HAPPENED A FEW DAYS AGO..") kini bisa diterjemahkan lewat kotak manual (**B**): huruf beserta garis tepinya terhapus bersih, dan terjemahannya otomatis **putih dengan stroke hitam**.

## 1.6.3
- Perbaikan error **"'NoneType' object has no attribute 'write'"** saat OCR pertama kali dipakai di versi .exe (progres unduhan model kini dicatat ke `%APPDATA%\RexxaTranslator\rexxa.log`).
