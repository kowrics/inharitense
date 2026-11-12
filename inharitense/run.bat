@echo off
cd /d "%~dp0"
where py >nul 2>nul || (echo Python was not found. Install Python 3.10+ first.& pause & exit /b 1)
if not exist .venv py -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
pause
