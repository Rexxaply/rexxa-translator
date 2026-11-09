@echo off
REM Build lokal jadi aplikasi Windows (.exe). Rilis resmi dibuat otomatis oleh GitHub Actions.
cd /d "%~dp0"
call .venv\Scripts\activate.bat || (echo Jalankan setup_env.bat dulu & pause & exit /b 1)
pip install pyinstaller
python build.py || (echo. & echo [X] Build GAGAL - gulir ke atas untuk melihat error. & pause & exit /b 1)
echo.
echo ==========================================================
echo  Selesai: dist\RexxaTranslator\RexxaTranslator.exe
echo  Bagikan/zip seluruh folder dist\RexxaTranslator
echo ==========================================================
pause
