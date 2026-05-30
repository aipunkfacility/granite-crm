@echo off
set "PATH=%APPDATA%\Python\Python314\Scripts;%PATH%"
start "Granite Tunnel" cmd /c "%~dp0cloudflared.exe tunnel run"
start "Granite API" cmd /c "uv run cli.py api --reload"
cd granite-web
start "Granite Web" cmd /c "npm run dev"
