@echo off
chcp 65001 >nul
title ĐĂNG NHẬP THÊM TÀI KHOẢN GOOGLE DRIVE (+15GB MIỄN PHÍ)
cd /d "D:\AT\Tiktoktodropbox"

echo ============================================================
echo   🚀 CÔNG CỤ THÊM NICK GOOGLE DRIVE PHỤ (+15GB MIỄN PHÍ)
echo ============================================================
echo.
echo Nhập số thứ tự tài khoản bạn muốn thêm (Ví dụ: 2, 3, 4):
set /p acc_num="So thu tu tai khoan [mac dinh la 2]: "
if "%acc_num%"=="" set acc_num=2

set token_name=token_drive%acc_num%.json
echo.
echo 📁 File token se duoc luu vao: tokens\%token_name%
echo 👉 Dang khoi dong trinh duyet...
echo.

python tools\get_token.py --output %token_name%

echo.
echo ============================================================
pause
