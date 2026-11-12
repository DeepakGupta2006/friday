@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run run.bat once first to set things up.
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"
pip install -q flask
python server.py
pause
