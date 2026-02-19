# NB_Tech_Sys - 技術サポート RAG システム

NotebookLM 風の 3 パネルレイアウト（ソース｜チャット｜スタジオ）で、社内技術ドキュメントに対して対話的に質問できる RAG システムです。

## 特徴

- **NotebookLM 風 UI**: ソース管理・チャット・スタジオの 3 パネル構成
- **マルチフォーマット対応**: PDF / DOCX / PPTX / TXT をドラッグ＆ドロップ
- **高品質な日本語**: Qwen2.5 (3B) による自然な日本語回答 + multilingual-e5 ベクトル検索
- **ローカル LLM**: Ollama 経由でローカル実行（API キー不要）
- **ソース個別管理**: チェックで参照対象を選択、✕ ボタンで個別削除
- **スタジオ一括生成**: 要約・FAQ・仕様一覧・トラブル対応を 200 文字程度でワンクリック生成
- **参照元表示**: 回答根拠となったドキュメント・ページ番号を提示

## システム要件

### ハードウェア

| 項目 | 最低要件 | 推奨環境 |
|------|---------|---------|
| **CPU** | 4 コア以上 | 8 コア以上 |
| **メモリ (RAM)** | 8 GB | 16 GB 以上 |
| **ストレージ** | 10 GB 空き | 20 GB 以上の空き |
| **GPU (VRAM)** | 不要（CPU のみで動作） | CUDA 対応 GPU 8 GB 以上で高速化 |

### メモリ内訳（目安）

| コンポーネント | メモリ使用量 |
|--------------|------------|
| Ollama + qwen2.5:3b | 約 5 GB |
| 埋め込みモデル (multilingual-e5-base) | 約 1 GB |
| PyTorch ランタイム | 約 0.5 - 2 GB |
| Streamlit + Python | 約 0.3 - 0.5 GB |
| **合計（概算）** | **約 7 - 9 GB** |

> **注意**: アップロードするドキュメントの量が多い場合、インデックス構築時に追加メモリが必要です。大量のドキュメント（100 ファイル以上）を扱う場合は 16 GB 以上を推奨します。

### ソフトウェア

| 項目 | 要件 |
|------|-----|
| **OS** | Windows 10/11、macOS、Linux |
| **Python** | 3.10 以上 |
| **Ollama** | 最新版（LLM 実行に必須） |
| **ブラウザ** | Chrome / Edge / Firefox（モダンブラウザ） |

## 技術スタック

| コンポーネント | 技術 |
|--------------|------|
| UI | Streamlit |
| 埋め込みモデル | intfloat/multilingual-e5-base（約 1 GB） |
| ベクトルストア | LlamaIndex VectorStoreIndex（ローカル永続化） |
| LLM | Ollama - qwen2.5:3b（デフォルト、約 5 GB） |
| RAG フレームワーク | LlamaIndex |
| ドキュメント解析 | PyPDF2 / python-docx / python-pptx |

## セットアップ

### 1. Ollama のインストール

[Ollama 公式サイト](https://ollama.ai) からインストールしてください。

インストール後、Ollama が起動していることを確認します：

```bash
ollama --version
```

> LLM モデル（qwen2.5:3b）はアプリ初回起動時に自動でダウンロードされます。手動で事前にダウンロードする場合:
> ```bash
> ollama pull qwen2.5:3b
> ```

### 2. Python 環境のセットアップ

```bash
cd NB_Tech_Sys

# 仮想環境を作成
python -m venv venv

# 仮想環境を有効化
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 依存ライブラリのインストール
pip install -r requirements.txt
```

### 3. アプリケーションの起動

```bash
streamlit run technical_support_rag.py
```

ブラウザで `http://localhost:8501` が自動的に開きます。

## 使い方

1. **ソースの追加**: 左パネルからドキュメント（PDF / DOCX / PPTX / TXT）をドラッグ＆ドロップでアップロード。読み込み完了後、アップローダーは自動クリアされます
2. **ソースの管理**: 「読み込み済みソース」一覧でチェックボックスから参照対象を選択。✕ ボタンで個別削除も可能
3. **質問の入力**: チャット欄に質問を入力して Enter
4. **スタジオで一括生成**: 右パネルのボタン（要約 / FAQ / 仕様一覧 / トラブル対応）をクリックすると、200 文字程度の簡潔な回答をチャット上に生成
5. **回答の確認**: チャット内で回答と参照元を確認。会話は JSON でエクスポート可能

## 対応ファイル形式

| 形式 | 拡張子 | 備考 |
|------|--------|------|
| PDF | `.pdf` | ページ番号付きで参照 |
| Word | `.docx` | 段落単位で分割 |
| PowerPoint | `.pptx` | スライド番号付きで参照 |
| テキスト | `.txt` | プレーンテキスト |

## プロジェクト構造

```
NB_Tech_Sys/
├── technical_support_rag.py   # メインアプリケーション
├── requirements.txt           # 依存ライブラリ
├── README.md                  # このファイル
├── uploaded_sources/          # アップロードされたドキュメント（自動生成）
└── storage/                   # ベクトルインデックス（自動生成）
```
