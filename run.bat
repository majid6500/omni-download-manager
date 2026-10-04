@echo off
rem Creates a virtual environment on first run, installs dependencies and starts Omni Download Manager.
cd /d "%~dp0"
if not exist .venv (
    py -3 -m venv .venv || goto :error
    call .venv\Scripts\python -m pip install --upgrade pip || goto :error
    call .venv\Scripts\python -m pip install -r requirements.txt || goto :error
)
start "" .venv\Scripts\pythonw.exe -m omni_download_manager
exit /b 0
:error
echo Setup failed. Make sure Python 3.10+ is installed ("py -3 --version").
pause
exit /b 1
