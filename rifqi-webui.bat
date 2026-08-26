@echo off
setlocal
set "CURRENT_DIR=%~dp0"
cd /d "%CURRENT_DIR%"
set "PYTHONPATH=%CURRENT_DIR%"

if not defined MPT_RIFQI_WEBUI_HOST set "MPT_RIFQI_WEBUI_HOST=127.0.0.1"
if not defined MPT_RIFQI_WEBUI_PORT set "MPT_RIFQI_WEBUI_PORT=8502"

set "STREAMLIT_CMD="
if exist "%CURRENT_DIR%.venv\Scripts\python.exe" (
    set "STREAMLIT_CMD="%CURRENT_DIR%.venv\Scripts\python.exe" -m streamlit"
) else if exist "%CURRENT_DIR%lib\python\python.exe" (
    set "STREAMLIT_CMD="%CURRENT_DIR%lib\python\python.exe" -m streamlit"
) else (
    where uv >nul 2>nul
    if not errorlevel 1 set "STREAMLIT_CMD=uv run streamlit"
)

if not defined STREAMLIT_CMD (
    where streamlit >nul 2>nul
    if not errorlevel 1 set "STREAMLIT_CMD=streamlit"
)

if not defined STREAMLIT_CMD (
    echo ***** MoneyPrinterTurbo dependencies were not found. *****
    echo ***** Install the project first, then run this file again. *****
    pause
    exit /b 1
)

echo.
echo =====================================================
echo   MoneyPrinterTurbo - Rifqi Edition
echo   http://%MPT_RIFQI_WEBUI_HOST%:%MPT_RIFQI_WEBUI_PORT%
echo =====================================================
echo.

%STREAMLIT_CMD% run .\webui\Rifqi.py --server.address=%MPT_RIFQI_WEBUI_HOST% --server.port=%MPT_RIFQI_WEBUI_PORT% --browser.serverAddress=%MPT_RIFQI_WEBUI_HOST% --browser.gatherUsageStats=False --client.toolbarMode=minimal --logger.hideWelcomeMessage=True --server.showEmailPrompt=False --server.enableCORS=True

if errorlevel 1 (
    echo.
    echo ***** Rifqi WebUI stopped with an error. *****
    pause
)
