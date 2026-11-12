@echo off
rem Starts Friday quietly for auto-start at login. Restarts her only if she crashes.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run run.bat once first to set things up.
    pause
    exit /b 1
)
rem Give Windows, the microphone and Ollama time to come up after login.
timeout /t 15 /nobreak >nul
call ".venv\Scripts\activate.bat"
:again
python main.py
if errorlevel 1 (
    echo Friday stopped unexpectedly. Restarting in 5 seconds...
    timeout /t 5 /nobreak >nul
    goto again
)
