@echo off
title SmartCampus AI - Launcher

echo ============================================
echo   SmartCampus AI - Full Stack Launcher
echo ============================================
echo.

echo [1/3] Starting Backend (Flask + SocketIO) on http://127.0.0.1:5000 ...
start "SmartCampus Backend" cmd /k "cd /d %~dp0smart-campus-backend && C:\Users\Admin\anaconda3\envs\croud\python.exe run.py"

echo Waiting for backend health check...
powershell -NoProfile -Command "for ($i=0; $i -lt 30; $i++) { try { $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/api/health -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {} Start-Sleep -Seconds 1 } exit 1"
if %ERRORLEVEL% EQU 0 (
  echo Backend is ready!
  echo.
  echo [2/3] Frontend Dashboard is now LIVE at:
  echo          http://127.0.0.1:5000
  echo.
  echo Opening dashboard in your default browser...
  start http://127.0.0.1:5000
) else (
  echo Backend did not become ready in time.
)

echo.
echo [3/3] You can start Gate Monitor manually:
echo          cd gate_monitor
echo          C:\Users\Admin\anaconda3\envs\croud\python.exe main.py
echo.
echo          Or for multi-gate demo:
echo          C:\Users\Admin\anaconda3\envs\croud\python.exe multi_gate_runner.py
echo.
echo ============================================
echo   Dashboard    : http://127.0.0.1:5000
echo   Backend API  : http://127.0.0.1:5000/api
echo   Admin Panel  : http://127.0.0.1:5000 (Admin Settings tab)
echo   WebSocket    : ws://127.0.0.1:5000/ws/traffic
echo ============================================
echo.
echo   INSTRUCTIONS:
echo   1. Backend + Frontend are now running together!
echo   2. Dashboard should have opened in your browser
echo   3. If not, open: http://127.0.0.1:5000
echo   4. Start gate monitor in another terminal to send live data
echo.
echo   To test WebSocket alerts:
echo   - Go to Admin Settings tab in dashboard
echo   - Set gate capacity to a low number (e.g., 10)
echo   - Start gate monitor and watch for redirection alerts!
echo.
pause
