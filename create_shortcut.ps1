$desktopDir = "D:\Files\Desktop"
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$desktopDir\DongBoTikTokDropbox.lnk")
$Shortcut.TargetPath = "d:\AT\Tiktoktodropbox\CHAY_DONG_BO_TIKTOK.bat"
$Shortcut.WorkingDirectory = "d:\AT\Tiktoktodropbox"
$Shortcut.IconLocation = "d:\AT\Tiktoktodropbox\app_icon.ico"
$Shortcut.Save()
Write-Host "Da tao shortcut tren Desktop thanh cong!"
