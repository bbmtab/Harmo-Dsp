@echo off
REM Harmo-Dsp launcher. Absolute python path: scheduled-task contexts
REM do NOT inherit the interactive PATH (silent-failure root cause).
set PY=E:\Python313\python.exe
if not exist "%PY%" (
  echo Python not found at %PY% - edit this bat to point at your python.exe
  pause
  exit /b 1
)
cd /d "%~dp0"
echo [%date% %time%] launching > "%TEMP%\harmo-launch.log"
"%PY%" -m harmo_dsp >> "%TEMP%\harmo-launch.log" 2>&1
if errorlevel 1 (
  echo GUI exited with error - see %TEMP%\harmo-launch.log
  "%PY%" -m harmo_dsp --check
  pause
)
