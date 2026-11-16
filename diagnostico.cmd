@echo off
REM Windows launcher. Python 3 must be installed separately.
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 "%~dp0diagnostico.py" %*
) else (
    python "%~dp0diagnostico.py" %*
)
exit /b %errorlevel%
