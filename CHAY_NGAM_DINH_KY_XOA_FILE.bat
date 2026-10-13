@echo off
chcp 65001 >nul
title CHẠY NGẦM ĐỊNH KỲ: TỰ ĐỘNG XÓA FILE ĐÃ ĐĂNG
color 0B
cd /d "%~dp0"
echo ========================================================
echo   CHẾ ĐỘ TỰ ĐỘNG: KIỂM TRA VÀ DỌN DẸP MỖI 30 PHÚT
echo   (Để cửa sổ này thu nhỏ dưới thanh Taskbar)
echo ========================================================
python auto_clean_posted.py --loop --interval 1800
pause
