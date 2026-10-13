@echo off
chcp 65001 >nul
title DỌN DẸP FILE ĐÃ ĐĂNG TRÊN DRIVE & DROPBOX
color 0A
cd /d "%~dp0"
echo ========================================================
echo    TIẾN HÀNH QUÉT VÀ XÓA CÁC VIDEO ĐÃ ĐĂNG LÊN FACEBOOK
echo ========================================================
python auto_clean_posted.py
echo.
echo Đã hoàn tất! Cửa sổ này sẽ tự đóng sau 10 giây...
timeout /t 10 >nul
