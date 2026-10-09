@echo off
REM Harmo-Dsp launcher — double-click this on YOUR desktop session.
REM (Processes started by automation shells cannot show windows here.)
cd /d "%~dp0"
python -m harmo_dsp
if errorlevel 1 (
  echo.
  echo --- GUI failed to start. Run diagnostics: ---
  python -m harmo_dsp --check
  pause
)
