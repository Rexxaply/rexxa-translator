@echo off
REM Perbaikan cepat untuk error "operator torchvision::nms does not exist"
cd /d "%~dp0"
call .venv\Scripts\activate.bat || (echo Folder .venv tidak ada & pause & exit /b 1)
echo Versi sekarang:
python -c "import torch, torchvision; print(' torch', torch.__version__, '/ torchvision', torchvision.__version__)"
echo.
echo  [1] GPU NVIDIA (CUDA 12.1)
echo  [2] CPU saja
set /p CH=Pilih 1 atau 2:
set IDX=https://download.pytorch.org/whl/cpu
if "%CH%"=="1" set IDX=https://download.pytorch.org/whl/cu121
pip install --upgrade --force-reinstall --no-deps torch torchvision --index-url %IDX%
echo.
python -c "import torch, torchvision, torchvision.ops as o; o.nms(torch.zeros((1,4)), torch.zeros(1), 0.5); print('torch', torch.__version__, '/ torchvision', torchvision.__version__, 'OK')" && (
  echo.
  echo Berhasil. Coba run.bat dulu, lalu build_exe.bat.
) || echo [X] Masih gagal - kirim screenshot jendela ini.
pause
