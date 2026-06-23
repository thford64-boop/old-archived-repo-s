@echo off
:: YPlay tray launcher - fully portable, works from any location
setlocal

set "HERE=%~dp0"
set "SCRIPT=%HERE%yplay_tray.pyw"

:: Find pythonw.exe (no console window) next to whichever python the
:: 'py' launcher or PATH resolves to. Fall back to 'py'/'python' with
:: a hidden window if pythonw can't be located.

set "PYW="

:: Try py launcher's reported install location first
for /f "delims=" %%P in ('py -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" 2^>nul') do (
    if exist "%%P" set "PYW=%%P"
)

if not defined PYW (
    for /f "delims=" %%P in ('python -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" 2^>nul') do (
        if exist "%%P" set "PYW=%%P"
    )
)

if not defined PYW (
    where pythonw >nul 2>nul
    if %errorlevel%==0 set "PYW=pythonw"
)

if not defined PYW (
    echo pythonw.exe not found. Make sure Python 3.10+ is installed.
    pause
    exit /b 1
)

start "" "%PYW%" "%SCRIPT%"
