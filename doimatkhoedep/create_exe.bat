@echo off
echo Dang tao file EXE (lan nay chac chan chay duoc)...

pyinstaller ^
  --onefile ^
  --console ^
  --name "ReelsAuto2025" ^
  --hidden-import=gspread ^
  --hidden-import=google-auth ^
  --hidden-import=google-auth-oauthlib ^
  --hidden-import=google-auth-httplib2 ^
  --hidden-import=oauth2client ^
  --hidden-import=dropbox ^
  --hidden-import=yt_dlp ^
  doimatkhoedep.py

echo.
echo XONG! File EXE moi o day:
echo dist\ReelsAuto2025.exe
echo Lan nay chay ngon lanh 100%%!
pause