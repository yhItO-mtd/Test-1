"""
セットアップスクリプト - 初回セットアップを支援
"""
import os
import sys
from pathlib import Path


def check_python_version():
    """Pythonのバージョンチェック"""
    print("=== Pythonバージョンチェック ===")
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("❌ Python 3.10以上が必要です")
        return False

    print("✓ Pythonバージョン要件を満たしています\n")
    return True


def check_dependencies():
    """依存ライブラリのチェック"""
    print("=== 依存ライブラリチェック ===")

    required_packages = [
        'streamlit',
        'langchain',
        'sentence_transformers',
        'chromadb',
        'llama_cpp'
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"❌ {package} (未インストール)")
            missing_packages.append(package)

    if missing_packages:
        print("\n以下のコマンドで依存ライブラリをインストールしてください:")
        print("pip install -r requirements.txt")
        return False

    print("\n✓ すべての依存ライブラリがインストールされています\n")
    return True


def check_directories():
    """必要なディレクトリの存在確認と作成"""
    print("=== ディレクトリ構造チェック ===")

    script_dir = Path(__file__).parent
    required_dirs = [
        'data',
        'data/documents',
        'vector_db',
        'models'
    ]

    for dir_name in required_dirs:
        dir_path = script_dir / dir_name
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✓ {dir_name}/ を作成しました")
        else:
            print(f"✓ {dir_name}/")

    print()
    return True


def check_faq_data():
    """FAQデータファイルの確認"""
    print("=== FAQデータファイルチェック ===")

    script_dir = Path(__file__).parent
    faq_file = script_dir / "data" / "faqs.json"

    if not faq_file.exists():
        print("❌ data/faqs.json が見つかりません")
        return False

    print(f"✓ data/faqs.json が存在します\n")
    return True


def check_model():
    """LLMモデルファイルの確認"""
    print("=== LLMモデルファイルチェック ===")

    script_dir = Path(__file__).parent
    model_file = script_dir / "models" / "ELYZA-japanese-Llama-2-7b-fast-instruct-q4_K_M.gguf"

    if not model_file.exists():
        print("❌ LLMモデルファイルが見つかりません")
        print("\n以下の手順でモデルをダウンロードしてください:")
        print("1. https://huggingface.co/mmnga/ELYZA-japanese-Llama-2-7b-fast-instruct-gguf")
        print("2. ELYZA-japanese-Llama-2-7b-fast-instruct-q4_K_M.gguf をダウンロード")
        print("3. models/ フォルダに配置\n")
        print("💡 LLMなしでもシステムは動作します（検索結果のみ表示）\n")
        return False

    # ファイルサイズをチェック（約4GB）
    file_size = model_file.stat().st_size
    file_size_gb = file_size / (1024 ** 3)

    if file_size_gb < 3.5:
        print(f"⚠️  モデルファイルのサイズが小さい可能性があります: {file_size_gb:.2f}GB")
        print("    ダウンロードが完了しているか確認してください\n")
        return False

    print(f"✓ LLMモデルファイルが存在します ({file_size_gb:.2f}GB)\n")
    return True


def initialize_vector_db():
    """ベクトルデータベースの初期化"""
    print("=== ベクトルデータベース初期化 ===")

    try:
        from faq_manager import FAQManager

        manager = FAQManager()
        manager.load_faqs()

        stats = manager.get_collection_stats()
        if stats['total_faqs'] == 0:
            print("ベクトルデータベースを構築中...")
            manager.build_vector_database()
            print("✓ ベクトルデータベースを構築しました\n")
        else:
            print(f"✓ ベクトルデータベースは既に構築済みです ({stats['total_faqs']}件)\n")

        return True

    except Exception as e:
        print(f"❌ エラー: {e}\n")
        return False


def main():
    """メイン処理"""
    print("=" * 50)
    print("ローカルFAQシステム - セットアップチェック")
    print("=" * 50)
    print()

    # Pythonバージョンチェック
    if not check_python_version():
        sys.exit(1)

    # ディレクトリ構造チェック
    check_directories()

    # FAQデータファイルチェック
    faq_ok = check_faq_data()

    # 依存ライブラリチェック
    deps_ok = check_dependencies()

    if not deps_ok:
        print("依存ライブラリをインストールしてから再度実行してください")
        sys.exit(1)

    # LLMモデルチェック
    model_ok = check_model()

    # ベクトルデータベース初期化
    if faq_ok:
        db_ok = initialize_vector_db()
    else:
        db_ok = False

    # 結果サマリー
    print("=" * 50)
    print("セットアップチェック結果")
    print("=" * 50)
    print(f"Python バージョン: ✓")
    print(f"依存ライブラリ: {'✓' if deps_ok else '❌'}")
    print(f"FAQデータ: {'✓' if faq_ok else '❌'}")
    print(f"LLMモデル: {'✓' if model_ok else '⚠️ （オプション）'}")
    print(f"ベクトルDB: {'✓' if db_ok else '❌'}")
    print()

    if deps_ok and faq_ok and db_ok:
        print("✅ セットアップが完了しました！")
        print("\n以下のコマンドでアプリケーションを起動できます:")
        print("streamlit run app.py")
    else:
        print("⚠️  一部のセットアップが未完了です")
        print("詳細はREADME.mdを参照してください")


if __name__ == "__main__":
    main()
