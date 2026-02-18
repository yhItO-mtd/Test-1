@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ============================================
echo  NB_Tech_Sys - セットアップ
echo ============================================
echo.

REM Python 存在確認
python --version >nul 2>&1
if errorlevel 1 (
    echo エラー: Python が見つかりません。Python 3.10以上をインストールしてください。
    pause
    exit /b 1
)

REM 仮想環境作成
echo [1/4] 仮想環境を作成しています...
python -m venv venv
if errorlevel 1 (
    echo エラー: 仮想環境の作成に失敗しました。
    pause
    exit /b 1
)
call venv\Scripts\activate

REM パッケージインストール
echo.
echo [2/4] パッケージをインストールしています...
pip install -r requirements.txt
if errorlevel 1 (
    echo エラー: パッケージのインストールに失敗しました。
    pause
    exit /b 1
)

REM Ollama確認
echo.
echo [3/4] Ollama の確認
echo -----------------------------------------------
echo Ollama がインストールされていない場合は、
echo 以下のURLからダウンロードしてください:
echo https://ollama.ai/download
echo -----------------------------------------------
pause

REM モデルダウンロード
echo.
echo [4/4] LLMモデルをダウンロードしています...
ollama pull llama3.1:8b
if errorlevel 1 (
    echo 警告: モデルのダウンロードに失敗しました。Ollama が起動しているか確認してください。
    pause
)

echo.
echo ============================================
echo  セットアップ完了！
echo  run.bat をダブルクリックして起動してください
echo ============================================
pause
