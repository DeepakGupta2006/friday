@echo off
setlocal
cd /d "%~dp0"
set "LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Friday.lnk"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK); $s.TargetPath='%~dp0start_friday.bat'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Save()"
if exist "%LNK%" (
    echo.
    echo Done. Friday will now start by herself every time you sign in to Windows.
    echo To test it, restart your PC, or double-click start_friday.bat.
) else (
    echo Could not create the shortcut.
)
pause
