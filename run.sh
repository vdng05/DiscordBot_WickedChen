#!/usr/bin/env bash
# 1-Click Runner for Linux / VPS
set -e

echo "============================================================"
echo "  🏰 WICKEDCHEN CLAN DISCORD BOT - TRÌNH KHỞI CHẠY LINUX"
echo "============================================================"

# Kiểm tra Python
if ! command -v python3 &> /dev/null; then
    echo "[LỖI] Không tìm thấy python3! Vui lòng cài đặt: sudo apt update && sudo apt install python3 python3-pip"
    exit 1
fi

echo "[*] Đang cài đặt / cập nhật thư viện cần thiết..."
pip3 install -r requirements.txt --quiet || pip install -r requirements.txt --quiet

echo "[*] Đang khởi chạy bot..."
python3 main.py
