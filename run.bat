@echo off
chcp 65001 > nul
title WickedChen Clan Bot - Runner

echo ============================================================
echo   🏰 WICKEDCHEN CLAN DISCORD BOT - TRÌNH KHỞI CHẠY 1-CLICK
echo ============================================================
echo.

:: 1. Kiểm tra Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [LOI] Khong tim thay Python tren may cua ban!
    echo Vui long tai va cai dat Python 3.12+ tai: https://www.python.org/downloads/
    echo LUU Y: Khi cai dat, nho tich vao o "Add python.exe to PATH"!
    echo.
    pause
    exit /b 1
)

:: 2. Kiểm tra và cài đặt thư viện tự động
echo [*] Đang kiểm tra thư viện hệ thống...
python -m pip install --upgrade pip >nul 2>nul
python -m pip install -r requirements.txt >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [CANH BAO] Co loi khi cai thu vien tu dong, dang thu cai truc tiep...
    python -m pip install -r requirements.txt
)
echo [OK] Thư viện đã sẵn sàng!
echo.

:: 3. Chạy Bot
echo [*] Đang khởi chạy Bot...
echo.
python main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo ============================================================
    echo [CHU Y] Bot da dung lai hoac gap su co.
    echo Vui long xem thong bao loi o tren de xu ly hoac lien he Admin.
    echo ============================================================
    echo.
    pause
)
