@echo off
chcp 65001 >nul
title [AUTO] TikTok to Dropbox Downloader & Sync
color 0A

echo ======================================================================
echo           HỆ THỐNG TỰ ĐỘNG TẢI TIKTOK VÀ ĐỒNG BỘ DROPBOX
echo ======================================================================
echo  - Kênh theo dõi : hang_zhou102, funnyclip.viral, catorahub
echo  - Dropbox       : 2 Tài khoản tự động luân chuyển khi đầy
echo  - Cảnh báo      : Telegram (@hungleDKH)
echo  - Bảng tính     : Google Sheets (Suc khoe doi song 24h)
echo ======================================================================
echo.

cd /d "%~dp0"
python yt-tt-to-sheet-date.py

echo.
echo ======================================================================
echo  [HOÀN THÀNH / TẠM DỪNG] Nhấn phím bất kỳ để đóng cửa sổ này...
echo ======================================================================
pause >nul
