@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "VENV_DIR=%USERPROFILE%\.nb_tech_venv"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [エラー] 仮想環境が見つかりません。先に install.bat を実行してください。
    pause
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"

where streamlit >nul 2>&1
if errorlevel 1 (
    echo [エラー] streamlit が見つかりません。install.bat を再実行してください。
    pause
    exit /b 1
)

echo アプリを起動しています... ブラウザが開くまでお待ちください。
echo 終了するには Ctrl+C を押してください。
echo.
streamlit run technical_support_rag.py
echo.
echo アプリが終了しました。
pause
