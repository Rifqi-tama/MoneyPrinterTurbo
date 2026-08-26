@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title MoneyPrinterTurbo - Rifqi Edition

set "HOST=127.0.0.1"
set "PORT=8502"
set "PYTHONPATH=%CD%"

if not exist "config.toml" (
    if exist "config.example.toml" (
        copy /Y "config.example.toml" "config.toml" >nul
        echo [Rifqi Edition] Created config.toml from the default template.
    )
)

set "PYTHON_EXE="
if exist "%CD%\lib\python\python.exe" set "PYTHON_EXE=%CD%\lib\python\python.exe"
if not defined PYTHON_EXE if exist "%CD%\.venv\Scripts\python.exe" set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"

if not defined PYTHON_EXE (
    echo.
    echo ============================================================
    echo  Portable Python runtime was not found.
    echo  This launcher is intended for the Rifqi Portable package.
    echo ============================================================
    echo.
    pause
    exit /b 1
)

set "SELECTED_PORT="
for /f %%P in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "$preferred=%PORT%; $ports=@($preferred)+((8503..8599) | Where-Object {$_ -ne $preferred}); foreach($p in $ports){$l=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$p); try{$l.Start();$l.Stop();Write-Output $p;break}catch{try{$l.Stop()}catch{}}}"') do set "SELECTED_PORT=%%P"
if not defined SELECTED_PORT set "SELECTED_PORT=%PORT%"
set "PORT=%SELECTED_PORT%"

set "URL=http://%HOST%:%PORT%"
echo.
echo ============================================================
echo   MoneyPrinterTurbo - Rifqi Edition
 echo  %URL%
echo   Close this window to stop the local server.
echo ============================================================
echo.

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process '%URL%'"

"%PYTHON_EXE%" -m streamlit run ".\webui\Rifqi.py" --server.address=%HOST% --server.port=%PORT% --browser.serverAddress=%HOST% --browser.gatherUsageStats=False --client.toolbarMode=minimal --logger.hideWelcomeMessage=True --server.showEmailPrompt=False --server.enableCORS=True

if errorlevel 1 (
    echo.
    echo [Rifqi Edition] The WebUI stopped with an error.
    pause
)
