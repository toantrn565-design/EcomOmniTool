@echo off
chcp 65001 >nul
title Ecom OmniTool - Khoi Chay

echo ===================================================
echo =       KHOI DONG ECOM OMNITOOL (FastAPI)         =
echo ===================================================

echo Dang kiem tra moi truong...
python -m pip install -r requirements.txt >nul 2>&1
playwright install chromium >nul 2>&1

echo.
echo ===================================================
echo Dang don dep he thong (Tat tien trinh cu neu co)...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8888" ^| find "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
echo ===================================================
echo Tool dang chay! Vui long KHONG tat cua so nay.
echo Giao dien se tu dong mo tren trinh duyet...
echo ===================================
echo.

python main.py
pause
