# Catatan rilis

Format: setiap rilis punya bagian `## X.Y.Z`. Isi bagian ini otomatis tampil
di jendela "Update tersedia" dan di halaman Release GitHub. Simpan 5 versi terbaru saja.

## 1.13.0
- **Deteksi warna teks lebih pintar**: warna isi huruf, **garis tepi** (warna + tebal), dan **gradasi** atas→bawah dibaca langsung dari teks asli, lalu dipakai untuk terjemahan. Bekerja untuk huruf merah/emas bergradasi (manhwa), huruf putih bergaris tepi hitam, huruf berwarna bergaris tepi putih, dll. Huruf hitam yang buram tetap dianggap hitam.
- Warna dibaca juga saat **OCR** (termasuk kotak yang dibuat manual dan tombol "OCR ulang").
- Tombol baru **◉** di panel Tipografi: ambil warna dari teks asli untuk balon yang dipilih.
- Pembersihan latar putih lebih bersih: sisa tepi samar huruf berwarna tidak lagi tertinggal.

## 1.12.1
- Logo judul di **latar terang** (mis. judul Korea bergradasi emas-biru): huruf diberi garis tepi gelap agar terbaca, tekstur warna asli tetap dipakai.
- Pencocokan font tidak lagi memilih font simbol / tanpa huruf latin (huruf jadi kotak-kotak); logo judul mengutamakan font tebal.
- Huruf logo bergradasi tidak lagi dianggap "kuas kasar" (efek gores hanya untuk logo yang memang kasar).

## 1.12.0
- **Logo judul seri otomatis**: menu ⚡ (panah di tombol Terjemahkan) → **Logo judul seri di halaman ini…**, isi judul terjemahan sekali (mis. "Player yang Kembali Setelah 10.000 Tahun"). Logo asli dihapus lalu diganti logo terjemahan: kata penting besar, kata sambung kecil, huruf diisi tekstur & warna logo asli, tepi kasar seperti kuas, miring, dan bayangan.
- Setelah judul seri diisi, halaman judul di 3 halaman awal setiap chapter otomatis dikenali & diganti saat ⚡ Terjemahkan.
- Font logo dipilih otomatis yang paling mirip (font aplikasi → font perangkat). Kotak logo bisa digeser/diubah; jenis balon "Logo judul seri" juga bisa dipilih manual.

## 1.11.0
- **Teks spesial / SFX besar** (mis. "GET AWAY FROM HER!!" dengan huruf kuas tebal) kini dideteksi, dihapus rapi (hanya hurufnya, tanpa garis balon/gambar), lalu diganti terjemahan seukuran aslinya dan dimiringkan/diputar seperti aslinya.
- **Cocokkan font otomatis** untuk SFX: dipilih font yang bentuk hurufnya paling mirip (tebal goresan, kekasaran, miring, lebar). Dicari di font aplikasi dulu, lalu font perangkat (Windows\\Fonts); bila tidak ada yang sama, dipilih yang paling mirip. Tombol ✦ di sebelah pilihan font = cocokkan font untuk balon mana pun.
- SFX Jepang yang tidak terbaca sebagai kata (saat sumber Inggris) dibiarkan apa adanya.
- Pengaturan → Proses: nyalakan/matikan pencocokan font & pemakaian font perangkat.

## 1.10.0
- **Webtoon / strip panjang (manhwa & manhua)**: gambar yang jauh lebih tinggi dari lebarnya (.webp/.jpg/.png) kini terdeteksi dengan benar. Ukuran huruf diukur dari lebar strip, bukan tingginya (sebelumnya teks di strip panjang sama sekali tidak terdeteksi).
- Gambar beresolusi rendah (lebar < 700 px) otomatis diperbesar 2x saat deteksi, jadi teks kecil tetap tertangkap.
- Strip panjang ditampilkan **pas lebar** dan mulai dari atas; tampilan Asli & Hasil tetap bergulir bersamaan.
