@echo off
set "PYTHON=%~dp0.venv\Scripts\python.exe"
set "PIP=%~dp0.venv\Scripts\pip.exe"

echo ========================================================
echo   P2T Post-Refresh Automation - First Time Setup
echo ========================================================
echo.

"%PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python venv not found at %PYTHON%
    pause
    exit /b 1
)

echo [1/2] Installing Python dependencies...
"%PIP%" install flask flask-cors >nul 2>&1
echo       Done.
echo.
echo [2/3] Creating desktop shortcut with icon...
"%PYTHON%" "%~dp0create_shortcut.py"
echo       Done.

"%PYTHON%" -c "import os, pathlib; desktop=pathlib.Path.home()/'Desktop'; vbs=r'%VBS_PATH%'; ico=r'%ICON_PATH%'; wd=r'%PROJECT_DIR%'; ps=desktop/'_mkshortcut.ps1'; ps.write_text(f'$ws=New-Object -ComObject WScript.Shell;$s=$ws.CreateShortcut(\"'+str(desktop/'P2T Automation.lnk')+'\");$s.TargetPath=\"wscript.exe\";$s.Arguments=\"\"\"{vbs}\"\"\";$s.WorkingDirectory=\"{wd}\";$s.IconLocation=\"{ico}\";$s.Description=\"P2T Dashboard\";$s.Save()'); os.system(f'powershell -ExecutionPolicy Bypass -File \"{ps}\"'); ps.unlink()"
echo       Done.
echo [2/3] Verifying setup...
"%PYTHON%" -c "from flask import Flask; print('       Flask: OK')"
"%PYTHON%" -c "from flask_cors import CORS; print('       Flask-CORS: OK')"
"%PYTHON%" -c "from dotenv import load_dotenv; print('       python-dotenv: OK')"
"%PYTHON%" -c "from playwright.sync_api import sync_playwright; print('       Playwright: OK')"
echo.

echo ========================================================
echo   Setup Complete!
echo ========================================================
echo.
echo   To start: double-click launch_dashboard.vbs
echo   Or copy it to your Desktop and rename to "P2T Automation"
echo.
echo ========================================================
pause