@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo        AttendAI - Setup and Start
echo ==========================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher 'py' nahi mila. Python install karein aur installation mein Add Python to PATH select karein.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment ban raha hai...
  py -m venv .venv
  if errorlevel 1 goto error
)
echo Python packages install/check ho rahe hain...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo Browser mein http://127.0.0.1:5000 kholein.
echo App band karne ke liye is window mein Ctrl+C dabayein.
echo.
".venv\Scripts\python.exe" app.py
pause
exit /b 0
:error
echo Setup mein error aaya. Upar diya gaya error message dekhein.
pause
exit /b 1
