@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  NB_Tech_Sys - セットアップ
echo ============================================
echo.

REM Python 存在確認 + バージョン検証
python --version >nul 2>&1
if errorlevel 1 (
    echo [エラー] Python が見つかりません。Python 3.10以上をインストールしてください。
    pause
    exit /b 1
)

python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [エラー] Python 3.10以上が必要です。現在のバージョン:
    python --version
    pause
    exit /b 1
)

REM venv パス設定
set "VENV_DIR=%USERPROFILE%\.nb_tech_venv"

REM 仮想環境作成
echo [1/5] 仮想環境を作成しています...
echo   場所: %VENV_DIR%
python -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [エラー] 仮想環境の作成に失敗しました。
    pause
    exit /b 1
)
call "%VENV_DIR%\Scriptsctivate"

REM パッケージインストール
echo.
echo [2/5] パッケージをインストールしています...
pip install -r requirements.txt
if errorlevel 1 (
    echo [エラー] パッケージのインストールに失敗しました。
    pause
    exit /b 1
)

REM 埋め込みモデル事前ダウンロード
echo.
echo [3/5] AIモデルをダウンロードしています (約2GB、時間がかかります)...
python -c "from llama_index.embeddings.huggingface import HuggingFaceEmbedding; HuggingFaceEmbedding(model_name='intfloat/multilingual-e5-large', cache_folder='./models')"
if errorlevel 1 (
    echo [警告] AIモデルのダウンロードに失敗しました。初回起動時に自動ダウンロードされます。
    pause
)

REM Ollama確認
echo.
echo [4/5] Ollama の確認
echo -----------------------------------------------
echo Ollama は回答生成に必要なLLMエンジンです。
echo.
echo まだインストールしていない場合:
echo   1. https://ollama.ai/download を開く
echo   2. ダウンロードしてインストールする
echo   3. Ollama を起動する
echo.
echo 準備ができたら、任意のキーを押してください。
echo -----------------------------------------------
pause >nul

REM LLMモデルダウンロード
echo.
echo [5/5] LLMモデルをダウンロードしています...
ollama pull llama3.1:8b
if errorlevel 1 (
    echo.
    echo [警告] LLMモデルのダウンロードに失敗しました。
    echo Ollama が起動しているか確認してください。
    pause
)

echo.
echo ============================================
echo  セットアップ完了!
echo  run.bat をダブルクリックして起動してください。
echo ============================================
pause
