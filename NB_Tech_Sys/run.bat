@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "VENV_DIR=%USERPROFILE%\.nb_tech_venv"

if not exist "%VENV_DIR%\Scriptsctivate" (
    echo [エラー] 仮想環境が見つかりません。先に install.bat を実行してください。
    pause
    exit /b 1
)

call "%VENV_DIR%\Scriptsctivate"
streamlit run technical_support_rag.py
if errorlevel 1 (
    echo.
    echo エラーが発生しました。上記のメッセージを確認してください。
    pause
)
