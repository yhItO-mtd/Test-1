@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

if not exist "venv\Scripts\activate" (
    echo エラー: 仮想環境が見つかりません。先に install.bat を実行してください。
    pause
    exit /b 1
)

call venv\Scripts\activate
streamlit run technical_support_rag.py
if errorlevel 1 (
    echo.
    echo エラーが発生しました。上記のメッセージを確認してください。
    pause
)
