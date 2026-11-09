# Rexxa Translator

![Rexxa Translator](assets/logo.png)

Aplikasi Windows (.exe) untuk menerjemahkan manga / manhwa / manhua:
**deteksi balon → OCR → terjemah → hapus teks asli → typesetting**, dengan editor berdampingan
(Asli | Terjemahan) untuk merapikan hasil, dan **update otomatis** dari GitHub.

## Unduh & pasang

1. Buka halaman **[Releases](../../releases/latest)** dan unduh `RexxaTranslator-X.Y.Z-win64.zip`.
2. Ekstrak ke folder mana saja, buka `RexxaTranslator\RexxaTranslator.exe`.
3. Selesai. Versi baru akan ditawarkan otomatis di dalam aplikasi (**Update sekarang**).

Model OCR diunduh otomatis saat pertama kali dipakai (sekali, butuh internet).

## Fitur

| Tahap | Pilihan |
|---|---|
| Deteksi | Teks dulu lalu balon (OpenCV, cepat) · EasyOCR · Hybrid · kotak manual |
| OCR | manga-ocr (Jepang: vertikal, furigana) · EasyOCR (Korea, Mandarin, Inggris) |
| Terjemah | Google (gratis) · DeepL · LLM kompatibel OpenAI: Gemini, OpenAI, OpenRouter, Groq, LM Studio/Ollama |
| Hapus teks | Isi warna balon · OpenCV inpaint · LaMa AI |
| Typeset | Ukuran font otomatis, tanpa memotong kata, font/ukuran/warna/stroke/rata per balon |

Lainnya: tampilan Asli | Terjemahan sinkron, hasil diperbarui otomatis saat mengedit, batch satu
chapter, **glosarium**, simpan/buka proyek `.mtproj`, export CBZ/ZIP & skrip `.txt`, drag & drop, CLI.

## Cara pakai

1. Klik ikon folder (Ctrl+O) atau seret folder chapter ke jendela.
2. Pilih bahasa di toolbar (mis. `EN → ID`). Pilihan ini diingat.
3. Klik **⚡ Terjemahkan** (F5) untuk halaman ini, atau panah di sebelahnya → *Terjemahkan SEMUA* (F6).
4. Rapikan: klik balon di gambar ASLI → edit di panel **PROPERTI**. Sisi TERJEMAHAN ikut berubah.
   **B** = tambah kotak manual, **Delete** = hapus balon, PgUp/PgDn = ganti halaman.
5. Ikon export → **CBZ/ZIP**.

**Gemini (gratis, kualitas bagus):** API key dari aistudio.google.com → Pengaturan → Terjemahan →
*LLM*, preset *Gemini*. Data pribadi (pengaturan, API key, font) ada di `%APPDATA%\RexxaTranslator\`
dan tidak tersentuh oleh update.

## Cara kerja update

```
RexxaTranslator.exe + _internal\   MESIN: Python, Qt, OpenCV, PyTorch, OCR  (besar, jarang berubah)
app\  (core, gui, assets)          KODE APLIKASI                            (±0,5 MB, sering berubah)
```

- **Update cepat:** hanya `app\` yang diganti, lalu aplikasi restart. Versi lama disimpan di `app.old\`;
  kalau versi baru gagal dibuka, aplikasi otomatis kembali ke versi sebelumnya.
- **Update penuh:** bila mesin berubah (`ENGINE_VERSION` di `main.py` naik), seluruh aplikasi diunduh
  dan dipasang oleh skrip kecil setelah aplikasi tertutup.
- Unduhan diverifikasi dengan SHA-256 dari `update.json`.

## Merilis versi baru (untuk pengembang)

```
1. Ubah kode. Naikkan __version__ di core/version.py (mis. 1.5.0) dan tulis catatan di CHANGELOG.md
2. git commit -am "Rilis 1.5.0"
3. git tag v1.5.0
4. git push && git push --tags
```

GitHub Actions (`.github/workflows/release.yml`) lalu membangun .exe di Windows, mengujinya, dan
menerbitkan Release berisi `update.json`, zip kode, dan zip lengkap (±20–30 menit).
Jika menambah **pustaka pihak ketiga baru**, tambahkan juga ke `requirements*.txt` dan
`_bundle_hint()` di `main.py`, lalu naikkan `ENGINE_VERSION`.

## Menjalankan dari source

```
py -3.12 -m venv .venv
setup_env.bat        (paket inti)
install_ai.bat       (OCR & LaMa; Python 3.12/3.13 — 3.14+ belum didukung paket AI)
run.bat              (jalankan)        build_exe.bat   (build .exe lokal)
```
`fix_torch.bat` memperbaiki error `torchvision::nms does not exist`.

CLI: `python cli.py "D:\manga\chapter 12" --src ja --tgt id --engine llm --save ch12.mtproj`

## Struktur kode

```
main.py        peluncur (satu-satunya kode di dalam .exe), rollback, uji-mandiri
core/          detector · ocr · translator · inpaint · typeset · pipeline · models · paths
               version (cek rilis) · selfupdate (unduh & pasang update)
gui/           main_window · canvas · dialogs · updater · icons
build.py       build PyInstaller + paket rilis       .github/workflows/release.yml  CI rilis
```
