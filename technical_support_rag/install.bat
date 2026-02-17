@echo off
chcp 65001 >nul
echo ============================================
echo  Technical Support AI - Setup
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python が見つかりません。
    echo https://www.python.org/downloads/ からインストールしてください。
    pause
    exit /b 1
)

REM Create venv
echo [1/3] 仮想環境を作成中...
python -m venv venv
call venv\Scripts\activate

REM Install packages
echo [2/3] パッケージをインストール中...
pip install -r requirements.txt

REM Check Ollama
echo.
echo [3/3] Ollama の確認
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Ollama が見つかりません。
    echo https://ollama.ai/download からインストールしてください。
    echo インストール後、以下を実行してください:
    echo   ollama pull llama3.1:8b
    pause
    exit /b 0
)

echo Ollama モデルをダウンロード中...
ollama pull llama3.1:8b

echo.
echo ============================================
echo  セットアップ完了
echo  run.bat をダブルクリックして起動してください
echo ============================================
pause
