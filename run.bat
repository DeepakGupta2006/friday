@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment with Python 3.12...
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo.
        echo Could not find Python 3.12. Install it from:
        echo https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
        echo Tick "Add python.exe to PATH", then double-click run.bat again.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

if not exist ".venv\installed_v4.flag" (
    echo Installing packages ^(first time only, takes a few minutes^)...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Package install failed. Read the error above.
        pause
        exit /b 1
    )
    echo ok> ".venv\installed_v4.flag"
)

python check.py
if errorlevel 1 (
    pause
    exit /b 1
)

python main.py
pause
