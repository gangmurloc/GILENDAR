@echo off
cd /d %~dp0

:loop
"%~dp0.venv\Scripts\python.exe" bot.py
echo.
echo [%date% %time%] Bot exited (code %errorlevel%). Restarting in 5 seconds... (Ctrl+C to stop)
timeout /t 5 /nobreak >nul
goto loop
