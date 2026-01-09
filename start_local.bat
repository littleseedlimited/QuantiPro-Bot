@echo off
echo Killing any remaining Python processes...
taskkill /F /IM python.exe >nul 2>&1

echo Starting QuantiProBot API (Port 8000)...
start "QuantiAPI" cmd /k "python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"

echo Waiting 5 seconds for API...
timeout /t 5 /nobreak >nul

echo Starting QuantiProBot Telegram Client...
start "QuantiBot" cmd /k "python main.py"

echo Done. Check the two new windows.
