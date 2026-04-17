@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "DB_PATH=%PROJECT_ROOT%data\granite.db"
set "BACKUP_DIR=%PROJECT_ROOT%backups"

if not exist "%DB_PATH%" (
    echo [ERROR] DB not found: %DB_PATH%
    echo Run this bat from project root folder.
    exit /b 1
)

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

for /f "tokens=2 delims==" %%i in ('wmic os get localdatetime /value ^| find "="') do set "dt=%%i"
set "TS=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%_%dt:~8,2%-%dt:~10,2%-%dt:~12,2%"
set "BACKUP_FILE=%BACKUP_DIR%\granite_%TS%.db"

echo [%date% %time%] Hot backup ...
python "%~dp0backup_db.py" "%DB_PATH%" "%BACKUP_FILE%"

endlocal
