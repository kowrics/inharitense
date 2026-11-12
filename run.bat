@echo off
setlocal
cd /d "%~dp0"

rem Capstone demonstration mode: use the bundled/local SQLite database and bind only to this computer.
rem This script never resets or replaces inharitense.db.
set APP_ENV=development
set DATABASE_URL=
set HOST=127.0.0.1
set PORT=5000
if not defined SECRET_KEY set SECRET_KEY=ecmci-capstone-local-demo-secret-change-before-sharing

if not exist .venv\Scripts\python.exe goto create_venv
goto check_dependencies

:create_venv
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m venv .venv
) else (
  where python >nul 2>nul
  if errorlevel 1 goto no_python
  python -m venv .venv
)
if errorlevel 1 goto failed

:check_dependencies
.venv\Scripts\python.exe -c "import flask, werkzeug, openpyxl, reportlab" >nul 2>nul
if errorlevel 1 (
  echo Installing the application's required packages into the project-local .venv...
  .venv\Scripts\python.exe -m pip install -r requirements-capstone.txt
  if errorlevel 1 goto failed
)
echo Starting ECMCI in local capstone demonstration mode...
echo Database: %CD%\inharitense.db
.venv\Scripts\python.exe app.py
if errorlevel 1 goto failed
exit /b 0

:no_python
echo Python was not found. Install Python 3.12 or newer, then run this file again.
pause
exit /b 1
:failed
echo Setup or application startup failed. See the error above; the database was not reset.
pause
exit /b 1
