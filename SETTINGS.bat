@echo off
setlocal
cd /d "%~dp0"

if not exist "config.toml" (
    if exist "config.example.toml" copy /Y "config.example.toml" "config.toml" >nul
)

if exist "%CD%\webui.bat" (
    call "%CD%\webui.bat"
    exit /b %errorlevel%
)

set "PYTHON_EXE="
if exist "%CD%\lib\python\python.exe" set "PYTHON_EXE=%CD%\lib\python\python.exe"
if not defined PYTHON_EXE if exist "%CD%\.venv\Scripts\python.exe" set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"

if not defined PYTHON_EXE (
    echo Portable Python runtime was not found.
    pause
    exit /b 1
)

set "PYTHONPATH=%CD%"
"%PYTHON_EXE%" -m streamlit run ".\webui\Main.py" --server.address=127.0.0.1 --server.port=8501 --browser.gatherUsageStats=False --client.toolbarMode=minimal
