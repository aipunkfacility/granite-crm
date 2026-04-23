@echo off
start "Granite API" cmd /c "uv run cli.py api --reload"
cd granite-web
start "Granite Web" cmd /c "npm run dev"
