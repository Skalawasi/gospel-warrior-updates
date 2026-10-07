@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 goto :error
py update_server.py --host 127.0.0.1 --port 8000
exit /b 0
:error
echo.
echo Could not install the updater requirements. Make sure Python 3 is installed.
pause
exit /b 1
