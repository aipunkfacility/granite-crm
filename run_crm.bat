@echo off
TITLE Granite CRM Launcher
echo ========================================
echo   GRANITE CRM - STARTER
echo ========================================

:: 1. Запуск Backend (FastAPI)
echo [1/2] Starting Backend (uv + FastAPI)...
start "Granite API" cmd /c "uv run cli.py api --reload"

:: 2. Запуск Frontend (Next.js)
echo [2/2] Starting Frontend (npm + Next.js)...
cd granite-web
start "Granite Web" cmd /c "npm run dev"

echo.
echo ----------------------------------------
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo ----------------------------------------
echo Press any key to stop this launcher (child windows will remain open).
pause > nul
