# ローカルFAQシステム

分析業務の新人や他部署担当者向けの、スタンドアロンPC上で動作するローカルFAQシステムです。

## 特徴

- ✅ **完全オフライン動作**: すべての処理をローカルPC上で実行
- 🇯🇵 **日本語対応**: multilingual-e5-largeとELYZA-Llama-2による日本語処理
- 💬 **対話的UI**: Streamlitによる使いやすいチャットインターフェース
- 🔍 **高精度検索**: ベクトル検索による意味的な質問マッチング
- 🤖 **自然な回答生成**: LLMによる要約・編集された対話的な回答
- 📚 **関連ドキュメント提示**: 回答とともに参考資料へのリンクを表示

## 技術スタック

| コンポーネント | 技術 |
|--------------|------|
| UI | Streamlit |
| 埋め込みモデル | multilingual-e5-large |
| ベクトルDB | ChromaDB |
| LLM | ELYZA-japanese-Llama-2-7b (GGUF) |
| LLM実行 | llama-cpp-python |
| 統合フレームワーク | LangChain |

## システム要件

- **OS**: Windows 10/11（Linux/Macでも動作可能）
- **Python**: 3.10以上
- **メモリ**: 8GB以上推奨
- **ストレージ**: 10GB以上の空き容量
- **CPU**: マルチコアCPU推奨（GPU不要）

## クイックスタート（Windows）

### ステップ1: プロジェクトのダウンロード

#### 方法A: GitHubからZIPダウンロード（推奨・簡単）

1. GitHubのリポジトリページにアクセス
2. 緑色の「Code」ボタンをクリック
3. 「Download ZIP」を選択
4. ダウンロードしたZIPファイルを解凍
5. 解凍したフォルダ内の `local_faq_system` フォルダを見つける

#### 方法B: Gitを使ってクローン（Gitがインストール済みの場合）

```cmd
rem 任意のフォルダで実行（例: C:\Users\YourName\）
git clone https://github.com/YOUR_USERNAME/Test-1.git
cd Test-1\local_faq_system
```

### ステップ2: セットアップと起動

#### 簡単な方法: エクスプローラーから開く

1. エクスプローラーで `local_faq_system` フォルダを開く
2. フォルダ内の空白部分で **Shiftキーを押しながら右クリック**
3. 「PowerShellウィンドウをここに開く」または「コマンドウィンドウをここで開く」を選択
4. 以下のコマンドを順番に実行：

```cmd
rem 仮想環境を作成
python -m venv venv

rem 仮想環境を有効化
venv\Scripts\activate

rem 依存ライブラリをインストール（初回のみ、5-10分かかります）
pip install -r requirements.txt

rem アプリケーションを起動
streamlit run app.py
```

#### コマンドプロンプトから実行する方法

コマンドプロンプトを開いて、以下を実行：

```cmd
rem 1. プロジェクトフォルダに移動（解凍した場所に合わせてパスを変更）
rem    例: C:\Users\yuhi2009\Downloads\Test-1\local_faq_system
cd パス\to\local_faq_system

rem 2. 仮想環境を作成
python -m venv venv

rem 3. 仮想環境を有効化
venv\Scripts\activate

rem 4. 依存ライブラリをインストール（初回のみ、5-10分かかります）
pip install -r requirements.txt

rem 5. アプリケーションを起動
streamlit run app.py
```

**ヒント**:
- `cd` コマンドで移動する代わりに、エクスプローラーでフォルダを開いてから右クリックする方が簡単です
- 仮想環境が有効化されると `(venv)` が表示されます

ブラウザで `http://localhost:8501` が自動的に開き、すぐに使い始められます（LLMなしモード）。

## セットアップ手順（詳細）

### 1. Pythonのインストール

Python 3.10以上がインストールされていることを確認してください。

**コマンドプロンプトで実行:**
```cmd
python --version
```

### 2. プロジェクトディレクトリへ移動

**コマンドプロンプトで実行:**
```cmd
cd local_faq_system
```

### 3. 仮想環境の作成と有効化

**Windows（コマンドプロンプト）:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python -m venv venv
source venv/bin/activate
```

### 4. 依存ライブラリのインストール

**コマンドプロンプトで実行:**
```cmd
pip install -r requirements.txt
```

**注意**: `llama-cpp-python`のインストールに時間がかかる場合があります（5-10分程度）。

### 5. LLMモデルのダウンロード

ELYZA-japanese-Llama-2-7bのGGUF形式モデルをダウンロードします。

#### オプション1: Hugging Faceから直接ダウンロード

1. [ELYZA-japanese-Llama-2-7b-fast-instruct-q4_K_M.gguf](https://huggingface.co/mmnga/ELYZA-japanese-Llama-2-7b-fast-instruct-gguf/resolve/main/ELYZA-japanese-Llama-2-7b-fast-instruct-q4_K_M.gguf) にアクセス
2. モデルファイルをダウンロード（約4GB）
3. `models/`フォルダに配置

#### オプション2: wgetを使用（Linux/Mac）

```bash
mkdir -p models
cd models
wget https://huggingface.co/mmnga/ELYZA-japanese-Llama-2-7b-fast-instruct-gguf/resolve/main/ELYZA-japanese-Llama-2-7b-fast-instruct-q4_K_M.gguf
cd ..
```

#### オプション3: Pythonスクリプトでダウンロード

```python
from huggingface_hub import hf_hub_download

model_path = hf_hub_download(
    repo_id="mmnga/ELYZA-japanese-Llama-2-7b-fast-instruct-gguf",
    filename="ELYZA-japanese-Llama-2-7b-fast-instruct-q4_K_M.gguf",
    local_dir="models"
)
```

### 6. 初期データベースの構築

FAQマネージャーを実行して、ベクトルデータベースを初期構築します。

**コマンドプロンプトで実行:**
```cmd
python faq_manager.py
```

以下のような出力が表示されれば成功です：

```
埋め込みモデル intfloat/multilingual-e5-large を読み込み中...
5件のFAQデータを読み込みました
埋め込みベクトルを生成中...
✓ 5件のFAQをベクトルデータベースに登録しました
```

## 使用方法

### アプリケーションの起動

**コマンドプロンプトで実行:**
```cmd
streamlit run app.py
```

ブラウザが自動的に開き、`http://localhost:8501` でアプリケーションが表示されます。

### 基本的な使い方

1. **質問の入力**: 画面下部の入力欄に質問を入力し、Enterキーを押します
2. **回答の表示**: 検索が実行され、関連するFAQに基づいた回答が表示されます
3. **関連ドキュメント**: 回答とともに参考資料へのリンクが表示されます

### 設定

サイドバーで以下の設定が可能です：

- **LLMで回答を生成**: チェックを入れると、LLMが自然な対話文を生成します（初回は時間がかかります）
- **FAQデータを更新**: FAQデータを追加・編集した後、このボタンでデータベースを更新します

## FAQデータの管理

### FAQデータの追加・編集

`data/faqs.json`ファイルを編集して、FAQデータを追加・変更できます。

**フォーマット例:**

```json
{
  "id": "faq006",
  "question": "新しい質問",
  "answer": "新しい回答内容です。",
  "related_docs": [
    {
      "title": "関連マニュアル",
      "path": "documents/manual.pdf"
    }
  ]
}
```

### データベースの更新

FAQデータを変更した後は、以下のいずれかの方法でデータベースを更新します：

**方法1: Streamlit UI から更新**
- アプリケーション実行中にサイドバーの「FAQデータを更新」ボタンをクリック

**方法2: コマンドプロンプトから更新**
```cmd
python faq_manager.py
```

### 関連ドキュメントの追加

関連ドキュメント（PDF、Word、PowerPointなど）は`data/documents/`フォルダに配置します。

```
data/
├── faqs.json
└── documents/
    ├── ftir_parameters.pdf
    ├── sample_prep.pdf
    └── analysis_manual.pdf
```

## トラブルシューティング

### LLMモデルが読み込めない

**エラー**: `モデルファイルが見つかりません`

**解決策**:
1. `models/`フォルダにGGUFファイルが存在するか確認
2. ファイル名が`ELYZA-japanese-Llama-2-7b-fast-instruct-q4_K_M.gguf`であることを確認
3. ファイルサイズが約4GBであることを確認（ダウンロードが完了しているか）

### 埋め込みモデルのダウンロードが遅い

初回起動時、`multilingual-e5-large`モデル（約2GB）が自動的にダウンロードされます。
ネットワーク速度によっては時間がかかる場合があります。

### メモリ不足エラー

LLMモデルの使用には約6-8GBのメモリが必要です。
メモリが不足する場合は、「LLMで回答を生成」のチェックを外して使用してください。

### ベクトルデータベースが空

**エラー**: `登録FAQ数: 0件`

**解決策**:
```cmd
python faq_manager.py
```
を実行して、データベースを再構築してください。

## パフォーマンス

### 処理時間の目安

| 処理 | 時間 |
|------|------|
| FAQ検索（ベクトル検索） | 1-2秒 |
| LLM回答生成（初回） | 10-15秒 |
| LLM回答生成（2回目以降） | 8-12秒 |
| モデル初回読み込み | 30-60秒 |

### パフォーマンスチューニング

`llm_handler.py`の以下のパラメータで調整可能です：

```python
LLMHandler(
    n_ctx=2048,        # コンテキストサイズ（小さくすると速くなる）
    n_threads=4,       # 使用するCPUスレッド数（CPUコア数に合わせる）
    temperature=0.7,   # 生成の多様性（低いほど安定）
    max_tokens=512     # 最大生成トークン数（少ないほど速い）
)
```

## プロジェクト構造

```
local_faq_system/
├── app.py                 # Streamlitメインアプリケーション
├── faq_manager.py         # FAQ管理とベクトル検索
├── llm_handler.py         # LLM回答生成
├── requirements.txt       # 依存ライブラリ
├── README.md             # このファイル
├── data/
│   ├── faqs.json         # FAQデータ（JSON形式）
│   └── documents/        # 関連ドキュメント
├── vector_db/            # ChromaDBデータ（自動生成）
└── models/               # LLMモデル（手動配置）
    └── ELYZA-japanese-Llama-2-7b-fast-instruct-q4_K_M.gguf
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

使用している主要なオープンソースコンポーネント:
- **ELYZA-japanese-Llama-2-7b**: Apache 2.0
- **multilingual-e5-large**: MIT
- **Streamlit**: Apache 2.0
- **ChromaDB**: Apache 2.0
- **llama-cpp-python**: MIT

## サポート

質問や問題が発生した場合は、以下の方法でお問い合わせください：

- 部署の担当者に連絡
- サポート窓口にメール
- プロジェクトのIssueトラッカー

## 今後の拡張予定

- [ ] ドキュメント内容の自動抽出と検索
- [ ] FAQの自動分類・タグ付け
- [ ] ユーザーフィードバック機能
- [ ] 質問履歴の保存と分析
- [ ] 複数言語対応

---

**バージョン**: 1.0.0
**最終更新**: 2025年10月
