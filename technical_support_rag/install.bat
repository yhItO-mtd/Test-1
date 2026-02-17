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
echo [1/4] 仮想環境を作成中...
python -m venv venv
call venv\Scripts\activate

REM Install packages
echo [2/4] パッケージをインストール中...
pip install -r requirements.txt

REM Check Tesseract (OCR)
echo.
echo [3/4] Tesseract OCR の確認
tesseract --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Tesseract OCR が見つかりません。
    echo スキャンPDFの読み取りに必要です。
    echo.
    echo インストール方法:
    echo   1. https://github.com/UB-Mannheim/tesseract/wiki からダウンロード
    echo   2. インストール時に Additional language data で Japanese と English を選択
    echo   3. インストール先を PATH に追加
    echo.
    echo テキスト埋め込みPDFのみ使用する場合は不要です。
    echo.
) else (
    echo Tesseract OK
    REM Check language data
    tesseract --list-langs 2>&1 | findstr "jpn" >nul
    if errorlevel 1 (
        echo [WARNING] 日本語 OCR データが見つかりません。
        echo Tesseract の jpn データをインストールしてください。
        echo   https://github.com/tesseract-ocr/tessdata
    ) else (
        echo 日本語 OCR データ OK
    )
    tesseract --list-langs 2>&1 | findstr "eng" >nul
    if errorlevel 1 (
        echo [WARNING] 英語 OCR データが見つかりません。
    ) else (
        echo 英語 OCR データ OK
    )
)

REM Check Ollama
echo.
echo [4/4] Ollama の確認
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Ollama が見つかりません。
    echo https://ollama.ai/download からインストールしてください。
    echo インストール後、以下を実行してください:
    echo   ollama pull qwen2.5:7b
    pause
    exit /b 0
)

echo.
echo 推奨モデル (qwen2.5:7b) をダウンロード中...
echo （日英バイリンガル対応・約4.7GB）
ollama pull qwen2.5:7b

echo.
echo ============================================
echo  セットアップ完了
echo  run.bat をダブルクリックして起動してください
echo.
echo  他のモデルも使用可能です（サイドバーで切替）:
echo    ollama pull qwen2.5:14b    (高精度、約9GB)
echo    ollama pull gemma2:9b      (多言語、約5.4GB)
echo    ollama pull llama3.1:8b    (英語中心、約4.7GB)
echo ============================================
pause
