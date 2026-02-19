@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "VENV_DIR=%USERPROFILE%\.nb_tech_venv"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [Error] venv not found. Please run install.bat first.
    pause
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"

where streamlit >nul 2>&1
if errorlevel 1 (
    echo [Error] streamlit not found. Please run install.bat again.
    pause
    exit /b 1
)

echo Starting NB_Tech_Sys...
echo Press Ctrl+C to stop.
echo.
streamlit run technical_support_rag.py
echo.
echo App stopped.
pause
