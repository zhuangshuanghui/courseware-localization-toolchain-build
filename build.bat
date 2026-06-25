@echo off
set "ROOT=%~dp0"
set "PROJECT=%ROOT%.."
set "VENV_PYTHON=%PROJECT%\.venv\Scripts\python.exe"

"%VENV_PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] .venv Python broken, falling back to system Python
    goto :use_system_python
)
set "PYTHON=%VENV_PYTHON%"
goto :python_found

:use_system_python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python or fix .venv
    pause
    exit /b 1
)
set "PYTHON=python"

:python_found

echo ============================================================
echo   Nuitka Encrypted Build
echo   Python: %PYTHON%
echo ============================================================
echo.

"%PYTHON%" "%ROOT%build_nuitka.py"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if %EXIT_CODE% EQU 0 (
    echo [OK] Build succeeded! Output in build\
    echo      Copy entire build\ to target PC, run start.bat
) else (
    echo [FAIL] Build failed, exit code: %EXIT_CODE%
)
pause
exit /b %EXIT_CODE%
