# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 1.26.0
- **Kembali ke layar awal**: menu ikon folder → "Kembali ke layar awal" menutup proyek yang sedang dibuka (ditanya simpan dulu bila ada perubahan) dan menampilkan layar awal lagi.
- **Riwayat proyek di menu ikon folder**: submenu **"Proyek terakhir"** berisi 10 proyek terbaru; klik untuk membuka (ditanya simpan dulu bila proyek sekarang belum disimpan). Ada juga "Hapus riwayat".
- Layar awal kini menampilkan **3 proyek terbaru** saja (berjajar di layar lebar). Tombol "Hapus riwayat" di layar awal sekarang berfungsi.

## 1.25.0
- **Proyek terakhir di layar awal**: 5 proyek .mtproj terbaru (yang pernah dibuka / disimpan) tampil di bawah tombol "Buka", lengkap dengan nama, folder, dan waktu terakhir diubah. Klik untuk langsung membuka; tombol × menghapusnya dari daftar (file proyeknya tidak dihapus). Proyek yang filenya sudah tidak ada otomatis disembunyikan.

## 1.24.0
- **Alat garis (L) kini pakai pratinjau yang bisa diedit**, seperti Pen Tool:
  - Klik = tambah titik, seret = gambar bebas (otomatis disederhanakan jadi beberapa titik), Shift = ruas lurus.
  - Hasilnya **garis putus-putus (pratinjau)** dulu, belum menempel di gambar.
  - **Seret titik** untuk mengubah bentuk, **Ctrl+klik / klik 2x di garis** = tambah titik, **klik 2x / Alt+klik titik** = hapus titik, **klik titik awal** = tutup bentuk, Backspace = hapus titik terakhir, Esc = buang pratinjau.
  - Garis otomatis **melengkung halus** melewati titik-titik (bisa dimatikan untuk garis patah lurus).
- Setelah pas, tekan **"Jadikan garis"** di toolbar (atau Enter, atau **klik kanan**): pilih jadikan garis, **jadikan balon (isi putih + garis tepi)**, atau isi putih saja.

## 1.23.0
- **OCR lebih pintar untuk teks bergaya** (judul, SFX, teks miring seperti "Mission Clear!"):
  - Teks **miring diluruskan** otomatis sebelum dibaca.
  - **Huruf berongga** (garis tepi hitam, isi putih) diisi gelap dulu supaya terbaca seperti huruf biasa.
  - Huruf kecil diperbesar, lalu dipilih hasil baca yang paling yakin.
- **Koreksi salah baca otomatis (teks Inggris)**: huruf yang mirip bentuknya dibetulkan memakai kamus ±170 ribu kata, misalnya GLEARIr → CLEAR!, AMUSlNG → AMUSING, D0ING → DOING, HERI → HER!. Nama tokoh yang tidak ada di kamus tidak diubah.
- Menu ⚡ → **Koreksi salah baca OCR (semua halaman)…**: memperbaiki teks proyek yang sudah ada, lalu bisa langsung **menerjemahkan ulang hanya balon yang berubah**.
- Penerjemah LLM kini juga diminta membetulkan salah baca OCR yang jelas sebelum menerjemahkan.

## 1.22.0
- **Alat garis (L)**: gambar garis sendiri, misalnya tepi balon yang hilang, tanpa healing brush. Seret = garis bebas (otomatis dihaluskan), **Shift + seret = garis lurus**. Tebal garis diatur di kolom ukuran (atau `[` `]`), warna di kotak warna sebelahnya. Bisa di-undo.
- **Gambar balon ulang**: buat bentuk dengan Shape tool (A, oval/kotak) atau Pen tool (P), lalu pilih **"Gambar balon: isi putih + garis tepi"** atau **"Gambar garis tepi saja"**.
- **Atur jumlah baris teks**: kolom baru **☰ baris** di panel Tipografi (+ tombol − / +). Auto = seperti biasa; angka = teks dibagi tepat sebanyak itu dengan panjang baris serata mungkin, ukuran huruf menyesuaikan. Tekan Enter di kolom terjemahan untuk memilih sendiri titik potong baris.
- **Tahan Spasi = mode tangan**: saat memakai alat apa pun (pen, shape, healing, garis, kotak), tahan Spasi lalu seret untuk menggeser gambar, lepas untuk kembali ke alat tadi.
- Tombol **Tambah kotak** dirapikan: panah pilihannya punya area sendiri, tidak menumpuk dengan ikon.
