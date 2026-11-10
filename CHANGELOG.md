# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 1.22.0
- **Alat garis (L)**: gambar garis sendiri, misalnya tepi balon yang hilang, tanpa healing brush. Seret = garis bebas (otomatis dihaluskan), **Shift + seret = garis lurus**. Tebal garis diatur di kolom ukuran (atau `[` `]`), warna di kotak warna sebelahnya. Bisa di-undo.
- **Gambar balon ulang**: buat bentuk dengan Shape tool (A, oval/kotak) atau Pen tool (P), lalu pilih **"Gambar balon: isi putih + garis tepi"** atau **"Gambar garis tepi saja"**.
- **Atur jumlah baris teks**: kolom baru **☰ baris** di panel Tipografi (+ tombol − / +). Auto = seperti biasa; angka = teks dibagi tepat sebanyak itu dengan panjang baris serata mungkin, ukuran huruf menyesuaikan. Tekan Enter di kolom terjemahan untuk memilih sendiri titik potong baris.
- **Tahan Spasi = mode tangan**: saat memakai alat apa pun (pen, shape, healing, garis, kotak), tahan Spasi lalu seret untuk menggeser gambar, lepas untuk kembali ke alat tadi.
- Tombol **Tambah kotak** dirapikan: panah pilihannya punya area sendiri, tidak menumpuk dengan ikon.

## 1.21.2
- **Kotak tersambung ke tombol Terjemahkan**: bila halaman sudah punya kotak (hasil deteksi atau kotak manual), tombol **Terjemahkan** (F5) dan **Terjemahkan SEMUA** (F6) kini **memakai kotak yang ada**, tidak mendeteksi ulang. Kotak yang belum punya teks di-OCR, yang belum punya terjemahan diterjemahkan, lalu halaman dirender. Teks & terjemahan yang sudah diedit tidak tertimpa.
- Alur baru yang enak: Deteksi balon semua halaman → tambah/hapus/rapikan kotak (mode "kotak saja") → Terjemahkan SEMUA.
- Untuk mengulang dari nol: menu ⚡ → **Terjemahkan ulang halaman ini dari awal (deteksi ulang)**.

## 1.21.1
- **Pilihan untuk kotak manual**: klik panah kecil di tombol "Tambah kotak" (B) untuk memilih apa yang dilakukan setelah kotak dibuat:
  - **Tambah kotak saja** (default baru): tidak menjalankan apa-apa, teks bisa diketik sendiri.
  - **Tambah kotak + OCR**: hanya membaca teks aslinya.
  - **Tambah kotak + OCR + terjemahkan**: perilaku lama.
  Pilihan disimpan. Kotak yang sudah dibuat tetap bisa di-OCR / diterjemahkan lewat tombol "OCR ulang" dan "Terjemah ulang" di panel Properti.

## 1.21.0
- **Layar awal baru**: saat aplikasi dibuka tanpa gambar, tampil layar "Buka gambar untuk mulai". Seret & lepas file/folder ke area itu, tekan Ctrl+O, atau klik tombol **Buka folder chapter / Buka gambar / Buka proyek**. Panel halaman & properti baru muncul setelah ada gambar.
- **Deteksi balon SEMUA halaman** (menu ⚡, Shift+F6): mendeteksi kotak teks di seluruh chapter sekaligus tanpa OCR/terjemah, jadi kotak bisa dicek dulu. Bila sebagian halaman sudah punya balon, pilih "Hanya yang belum" atau "Deteksi ulang semua".
- Nama default proyek baru kini **untitled.mtproj**.
- Ikon folder (buka/simpan) di toolbar selalu aktif.

## 1.20.0
- **Ikon file proyek**: file **.mtproj** kini punya ikon Rexxa Translator di Windows Explorer dan bisa dibuka dengan **klik ganda** (didaftarkan otomatis saat aplikasi dibuka, tanpa hak admin).
- **Simpan sebagai…** (Ctrl+Shift+S, di menu ikon folder): simpan proyek ke file baru, mis. untuk membuat cadangan / versi lain. File lama tetap seperti terakhir disimpan.
