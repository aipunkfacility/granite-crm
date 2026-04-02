@echo off
title Email Server - Granite CRM
cd /d "%~dp0"

if not exist "config.json" (
    echo ERROR: config.json not found!
    exit /b 1
)

python -m uvicorn server:app --host 127.0.0.1 --port 8000
