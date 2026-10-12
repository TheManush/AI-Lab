@echo off
echo ================================================
echo  BD Route Planner — Setup ^& Run
echo ================================================

cd /d "%~dp0backend"

echo.
echo [1/2] Installing Python dependencies...
pip install -r requirements.txt

echo.
echo [2/2] Starting Flask server...
echo      Opening http://127.0.0.1:5000 in your browser...
echo      (First run downloads Dhaka road network - takes ~30s)
echo      Press Ctrl+C to stop the server.
echo.

:: Open browser after a short delay (2 seconds for server to start)
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

python app.py

pause
