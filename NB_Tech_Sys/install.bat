@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  NB_Tech_Sys - Setup
echo ============================================
echo.

REM Check Python exists and version
python --version >nul 2>&1
if errorlevel 1 (
    echo [Error] Python not found. Please install Python 3.10 or later.
    pause
    exit /b 1
)

python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [Error] Python 3.10 or later is required. Current version:
    python --version
    pause
    exit /b 1
)

REM venv path
set "VENV_DIR=%USERPROFILE%\.nb_tech_venv"

REM Create virtual environment
echo [1/5] Creating virtual environment...
echo   Location: %VENV_DIR%
python -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [Error] Failed to create virtual environment.
    pause
    exit /b 1
)
call "%VENV_DIR%\Scripts\activate.bat"

REM Upgrade pip
echo.
echo [2/5] Installing packages...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo [Error] Failed to install packages.
    pause
    exit /b 1
)

REM Download embedding model
echo.
echo [3/5] Downloading AI model (about 2GB, this may take a while)...
python -c "from llama_index.embeddings.huggingface import HuggingFaceEmbedding; HuggingFaceEmbedding(model_name='BAAI/bge-m3', cache_folder='./models')"
if errorlevel 1 (
    echo [Warning] AI model download failed. It will be downloaded on first run.
    pause
)

REM Check Ollama
echo.
echo [4/5] Ollama Setup
echo -----------------------------------------------
echo Ollama is the LLM engine required for answers.
echo.
echo If not installed yet:
echo   1. Open https://ollama.ai/download
echo   2. Download and install
echo   3. Start Ollama
echo.
echo Press any key when ready.
echo -----------------------------------------------
pause >nul

REM Download LLM model
echo.
echo [5/5] Downloading LLM model...
ollama pull qwen2.5:3b
if errorlevel 1 (
    echo.
    echo [Warning] LLM model download failed.
    echo Please make sure Ollama is running.
    pause
)

echo.
echo ============================================
echo  Setup complete!
echo  Double-click run.bat to start the app.
echo ============================================
pause
