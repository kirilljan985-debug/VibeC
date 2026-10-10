@echo off
rem VibeC: поднять сервер портала и открыть браузер
chcp 65001 >nul
cd /d "%~dp0"
set VIBEC_OPEN_BROWSER=1
python server\app.py
pause
