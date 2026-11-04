@echo off
setlocal
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto install
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m venv .venv
) else (
  where python >nul 2>nul
  if errorlevel 1 goto no_python
  python -m venv .venv
)
if errorlevel 1 goto failed
:install
.venv\Scripts\python.exe -m ensurepip --upgrade
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe app.py
pause
exit /b 0
:no_python
echo Python was not found. Install Python 3.10+ first.
pause
exit /b 1
:failed
echo Setup did not finish. See the error above; the app has not been started.
pause
exit /b 1
