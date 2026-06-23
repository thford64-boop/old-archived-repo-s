@echo off
:: YPlay CLI wrapper - fully portable, works from any location
:: %~dp0 = the folder this .bat file lives in (with trailing backslash)
setlocal

set "HERE=%~dp0"
set "SCRIPT=%HERE%yplay.py"

:: Prefer 'py' launcher (always on PATH with standard Python installs),
:: fall back to 'python'
where py >nul 2>nul
if %errorlevel%==0 (
    py "%SCRIPT%" %*
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python "%SCRIPT%" %*
    ) else (
        echo Python not found in PATH. Install Python 3.10+ from https://python.org
        exit /b 1
    )
)
