@echo off
cd /d "%~dp0"

echo ============================================
echo  NB_Tech_Sys - セットアップ
echo ============================================
echo.

REM Python 存在確認 + バージョン検証 (BUG-1)
python --version >nul 2>&1
if errorlevel 1 (
    echo エラー: Python が見つかりません。Python 3.10以上をインストールしてください。
    pause
    exit /b 1
)

python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo エラー: Python 3.10以上が必要です。現在のバージョン:
    python --version
    pause
    exit /b 1
)

REM 仮想環境作成
echo [1/5] 仮想環境を作成しています...
python -m venv venv
if errorlevel 1 (
    echo エラー: 仮想環境の作成に失敗しました。
    pause
    exit /b 1
)
call venv\Scripts\activate

REM パッケージインストール
echo.
echo [2/5] パッケージをインストールしています...
pip install -r requirements.txt
if errorlevel 1 (
    echo エラー: パッケージのインストールに失敗しました。
    pause
    exit /b 1
)

REM 埋め込みモデル事前ダウンロード (UX-5)
echo.
echo [3/5] AIモデルをダウンロードしています（約2GB、数分かかります）...
python -c "from llama_index.embeddings.huggingface import HuggingFaceEmbedding; HuggingFaceEmbedding(model_name='intfloat/multilingual-e5-large', cache_folder='./models')"
if errorlevel 1 (
    echo 警告: AIモデルのダウンロードに失敗しました。初回起動時に自動ダウンロードされます。
    pause
)

REM Ollama確認 (UX-3 改善)
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
echo 準備ができたら任意のキーを押してください。
echo -----------------------------------------------
pause >nul

REM LLMモデルダウンロード
echo.
echo [5/5] LLMモデルをダウンロードしています...
ollama pull llama3.1:8b
if errorlevel 1 (
    echo.
    echo 警告: LLMモデルのダウンロードに失敗しました。
    echo Ollama が起動しているか確認してください。
    echo ※ アプリの文書検索機能は使えますが、回答生成にはOllamaが必要です。
    pause
)

echo.
echo ============================================
echo  セットアップ完了！
echo  run.bat をダブルクリックして起動してください
echo ============================================
pause
