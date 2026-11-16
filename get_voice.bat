@echo off
setlocal
cd /d "%~dp0"
rem 
rem   
rem  

if not exist ".venv\Scripts\python.exe" (
    echo Run run.bat once first so the environment exists, then run this again.
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"

set VOICE=en_GB-alan-medium
set VPATH=en/en_GB/alan/medium
if /i "%1"=="female" (
    set VOICE=en_GB-jenny_dioco-medium
    set VPATH=en/en_GB/jenny_dioco/medium
)

echo Installing Piper voice engine...
pip install piper-tts
if errorlevel 1 (
    echo.
    echo Could not install piper-tts. Friday will keep using the Windows voice.
    pause
    exit /b 1
)

if not exist "voices" mkdir voices
if exist "voices\%VOICE%.onnx" if exist "voices\%VOICE%.onnx.json" goto done

echo Downloading voice %VOICE% ^(about 60 MB^)...
pushd voices
python -m piper.download_voices %VOICE%
popd
if exist "voices\%VOICE%.onnx" if exist "voices\%VOICE%.onnx.json" goto done

echo First method failed, trying direct download...
set BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main/%VPATH%
curl.exe -L -f -o "voices\%VOICE%.onnx" "%BASE%/%VOICE%.onnx"
curl.exe -L -f -o "voices\%VOICE%.onnx.json" "%BASE%/%VOICE%.onnx.json"
if not exist "voices\%VOICE%.onnx.json" (
    echo.
    echo Download failed. Check your internet and run get_voice.bat again.
    pause
    exit /b 1
)

:done
echo.
echo Voice ready: %VOICE%
echo In config.py make sure this line matches:  PIPER_VOICE_NAME = "%VOICE%"
echo Then start Friday with run.bat
pause
