@echo off
REM Langkah 1: buat virtual environment + paket inti
cd /d "%~dp0"
where python >nul 2>nul || (echo Python belum terpasang. Unduh Python 3.11 dari python.org ^(centang "Add to PATH"^) & pause & exit /b 1)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Paket inti terpasang. Jalankan run.bat untuk mencoba aplikasi.
echo Untuk OCR (wajib untuk membaca teks), jalankan install_ai.bat
pause
