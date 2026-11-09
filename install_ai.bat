@echo off
REM Langkah 2: paket AI (OCR + LaMa). Pilih versi PyTorch sesuai GPU.
cd /d "%~dp0"
call .venv\Scripts\activate.bat || (echo Jalankan setup_env.bat dulu & pause & exit /b 1)

REM Paket AI belum tersedia untuk Python terlalu baru
python -c "import sys; sys.exit(0 if sys.version_info < (3,14) else 1)" || (
  echo.
  echo [!] Python di .venv terlalu baru untuk paket AI. Pakai Python 3.12:
  echo     rmdir /s /q .venv  lalu  py -3.12 -m venv .venv  lalu setup_env.bat
  pause & exit /b 1
)

echo.
echo  [1] Punya GPU NVIDIA (CUDA 12.1) - jauh lebih cepat
echo  [2] CPU saja
set /p CH=Pilih 1 atau 2:
set IDX=https://download.pytorch.org/whl/cpu
if "%CH%"=="1" set IDX=https://download.pytorch.org/whl/cu121

pip install -r requirements-ai.txt || goto :gagal
REM Pasang ulang torch + torchvision sebagai PASANGAN yang cocok
REM (paket lain kadang menarik versi torchvision yang berbeda -> error torchvision::nms)
pip install --upgrade --force-reinstall --no-deps torch torchvision --index-url %IDX% || goto :gagal
python -c "import torch, torchvision, torchvision.ops as o; o.nms(torch.zeros((1,4)), torch.zeros(1), 0.5); print('torch', torch.__version__, '/ torchvision', torchvision.__version__, 'OK')" || goto :gagal

echo.
echo Selesai. Model AI akan diunduh otomatis saat pertama kali dipakai (butuh internet sekali).
pause
exit /b 0

:gagal
echo.
echo [X] GAGAL. Gulir ke atas untuk melihat error merahnya, lalu kirim screenshot-nya.
pause
exit /b 1
