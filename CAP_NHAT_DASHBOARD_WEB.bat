@echo off
chcp 65001 >nul
title CẬP NHẬT TRANG WEB THEO DÕI GOOGLE DRIVE & SHEETS
color 0B
cd /d "%~dp0"

echo ========================================================
echo   TIẾN HÀNH DỌN DẸP FILE ĐÃ ĐĂNG VÀ CẬP NHẬT WEB MONITOR
echo ========================================================
python clean_and_update_web.py
echo.
echo 👉 Mở trang web xem ngay:
start docs\index.html
echo.
echo Đã hoàn tất! Cửa sổ này sẽ tự đóng sau 5 giây...
timeout /t 5 >nul
