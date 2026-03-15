# technical_support_rag.py
"""
NB_Tech_Sys - 技術サポートRAGシステム
NotebookLM 風 3パネルレイアウト: ソース | チャット | スタジオ
"""

import streamlit as st
from llama_index.core import (
    VectorStoreIndex,
    Document,
    Settings,
    StorageContext,
    load_index_from_storage,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
from pathlib import Path
import PyPDF2
import docx
from pptx import Presentation
import html
import json
import shutil
import os
import psutil
import urllib.request
from datetime import datetime

# メタデータフィルタ（ソース選択用）
try:
    from llama_index.core.vector_stores.types import (
        MetadataFilter,
        MetadataFilters,
        FilterCondition,
    )

    HAS_FILTERS = True
except ImportError:
    HAS_FILTERS = False

# スクリプトの配置ディレクトリを基準に絶対パスを使用
BASE_DIR = Path(__file__).parent
STORAGE_DIR = str(BASE_DIR / "storage")
METADATA_PATH = str(BASE_DIR / "storage" / "metadata.json")
CHAT_HISTORY_PATH = str(BASE_DIR / "storage" / "chat_history.json")
MODELS_DIR = str(BASE_DIR / "models")

# LLM モデル設定（メモリに合わせて変更可）
# qwen2.5:3b ≈ 2 GiB / qwen2.5:7b ≈ 4.5 GiB
OLLAMA_MODEL = "qwen2.5:3b"

# CPU物理コア数を取得（ハイパースレッドを除いた実コア数が最適）
CPU_THREADS = psutil.cpu_count(logical=False) or os.cpu_count() or 4

# 埋め込みモデル設定
# BAAI/bge-m3 ≈ 2 GiB（CJK特化、8192トークン対応）
EMBED_MODEL = "BAAI/bge-m3"

# ---------------------------------------------------------------------------
# ページ設定 & カスタムCSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="NB Tech Sys",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
/* --- NotebookLM-inspired theme --- */

/* Global background */
.stApp {
    background-color: #f8f6f1;
}

/* Sidebar (Sources panel) */
section[data-testid="stSidebar"] {
    background-color: #f0ece4;
}
section[data-testid="stSidebar"] .stDivider {
    border-color: #d8d4cc;
}

/* Chat messages */
[data-testid="stChatMessage"] {
    background-color: white;
    border-radius: 16px;
    border: 1px solid #e8e4dc;
    padding: 12px 16px;
}

/* Buttons - pill shape */
div[data-testid="stButton"] > button {
    border-radius: 20px !important;
    font-size: 0.85rem !important;
}

/* Studio action buttons (type=primary) */
div[data-testid="stButton"] > button[kind="primary"] {
    background-color: #e8f0fe !important;
    color: #1a73e8 !important;
    border: 1px solid #d2e3fc !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background-color: #d2e3fc !important;
}

/* Source count badge */
.source-badge {
    display: inline-block;
    background: #e8f0fe;
    color: #1a73e8;
    border-radius: 16px;
    padding: 2px 12px;
    font-size: 0.8rem;
    font-weight: 600;
}

/* Studio panel container */
.studio-container {
    background: white;
    border: 1px solid #e8e4dc;
    border-radius: 16px;
    padding: 20px;
}

/* Section header */
.panel-header {
    color: #1a73e8;
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 12px;
}

/* Source reference card in studio */
.ref-card {
    background: #f8f6f1;
    border: 1px solid #e8e4dc;
    border-radius: 12px;
    padding: 10px 14px;
    margin: 6px 0;
    font-size: 0.85rem;
}
.ref-card .ref-title {
    font-weight: 600;
    color: #1f1f1f;
}
.ref-card .ref-meta {
    color: #5f6368;
    font-size: 0.75rem;
}

/* Expander styling */
div[data-testid="stExpander"] {
    border-radius: 12px;
    border: 1px solid #e8e4dc;
}

/* Footer area */
.footer-bar {
    background: white;
    border-radius: 12px;
    border: 1px solid #e8e4dc;
    padding: 8px 16px;
    margin-top: 8px;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# セッション状態初期化
# ---------------------------------------------------------------------------

if "index" not in st.session_state:
    st.session_state.index = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "documents" not in st.session_state:
    st.session_state.documents = []
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "failed_files" not in st.session_state:
    st.session_state.failed_files = set()
if "selected_sources" not in st.session_state:
    st.session_state.selected_sources = set()

ICON_MAP = {
    "PDF": "📕",
    "DOCX": "📘",
    "PPTX": "📊",
    "TXT": "📄",
    "MD": "📝",
}


# ---------------------------------------------------------------------------
# モデル設定
# ---------------------------------------------------------------------------


@st.cache_resource
def setup_models():
    """埋め込みモデルとLLMを初期化する"""
    Settings.embed_model = HuggingFaceEmbedding(
        model_name=EMBED_MODEL,
        cache_folder=MODELS_DIR,
    )
    Settings.llm = Ollama(
        model=OLLAMA_MODEL,
        request_timeout=300.0,
        temperature=0.1,
        num_ctx=8192,
        additional_kwargs={"num_thread": CPU_THREADS},
        system_prompt=(
            "あなたは製品の技術サポート専門AIです。"
            "必ず自然な日本語で回答してください。\n"
            "以下のルールに従ってください：\n"
            "1. 提供された文書の情報のみを使用する\n"
            "2. 不明な場合は「文書に記載がありません」と回答\n"
            "3. 具体的なページ番号や章を引用する\n"
            "4. 技術用語は正確に使用する\n"
            "5. 簡潔で分かりやすく回答する"
        ),
    )
    return True


@st.cache_data(ttl=30)
def check_ollama_status():
    """Ollama の接続状態とモデル有無を確認する（30秒キャッシュ）"""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            models = [m["name"] for m in data.get("models", [])]
            model_base = OLLAMA_MODEL.split(":")[0]
            has_model = any(model_base in m for m in models)
            return True, has_model, models
    except Exception:
        return False, False, []


def pull_ollama_model(model_name):
    """Ollama モデルをダウンロードする（プログレス付き）"""
    payload = json.dumps({"name": model_name}).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/api/pull",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with st.status(
        f"LLMモデル `{model_name}` をダウンロード中...", expanded=True
    ) as status:
        progress_bar = st.progress(0, text="準備中...")
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    data = json.loads(line.decode("utf-8"))
                    msg = data.get("status", "")

                    total = data.get("total", 0)
                    completed = data.get("completed", 0)
                    if total > 0:
                        pct = completed / total
                        size_mb = total / (1024 * 1024)
                        done_mb = completed / (1024 * 1024)
                        progress_bar.progress(
                            pct,
                            text=f"{msg}  ({done_mb:.0f}/{size_mb:.0f} MB)",
                        )
                    else:
                        progress_bar.progress(0, text=msg)

            progress_bar.progress(1.0, text="ダウンロード完了")
            status.update(
                label=f"✅ `{model_name}` のセットアップ完了",
                state="complete",
                expanded=False,
            )
            return True
        except Exception as e:
            status.update(
                label=f"❌ ダウンロード失敗",
                state="error",
                expanded=True,
            )
            st.error(f"詳細: {e}")
            return False


with st.spinner("AIモデルを初期化中...（初回は数分かかります）"):
    setup_models()

# Ollama 接続チェック & 自動ダウンロード
ollama_ok, model_ok, available_models = check_ollama_status()
if not ollama_ok:
    st.warning(
        "⚠️ Ollama に接続できません。回答生成にはOllamaが必要です。\n\n"
        "1. Ollama をインストール: https://ollama.ai/download\n"
        "2. Ollama を起動してください"
    )
elif not model_ok:
    st.info(f"🔽 モデル `{OLLAMA_MODEL}` が未インストールです。自動ダウンロードを開始します...")
    if pull_ollama_model(OLLAMA_MODEL):
        st.rerun()

# 埋め込みモデル変更検知（モデルが変わったら旧インデックスを破棄）
_embed_marker = str(BASE_DIR / "storage" / ".embed_model")
if Path(_embed_marker).exists():
    _prev_model = Path(_embed_marker).read_text(encoding="utf-8").strip()
else:
    _prev_model = None

if Path(STORAGE_DIR).exists() and _prev_model != EMBED_MODEL:
    # 埋め込みモデルが変わったので旧インデックスは使えない
    shutil.rmtree(STORAGE_DIR)
    st.session_state.index = None
    st.session_state.documents = []
    st.session_state.selected_sources = set()
    st.info("埋め込みモデルが変更されたため、インデックスをリセットしました。ソースを再登録してください。")

# マーカーを書き出し
os.makedirs(STORAGE_DIR, exist_ok=True)
Path(_embed_marker).write_text(EMBED_MODEL, encoding="utf-8")

# 保存済みインデックスの自動読み込み
# METADATA_PATH はインデックス構築時のみ作成されるため、
# 空ディレクトリ（削除後の再作成等）では読み込みをスキップする
if st.session_state.index is None and Path(METADATA_PATH).exists():
    try:
        with st.spinner("保存済みデータを読み込み中..."):
            storage_context = StorageContext.from_defaults(
                persist_dir=STORAGE_DIR
            )
            st.session_state.index = load_index_from_storage(storage_context)
            if Path(METADATA_PATH).exists():
                with open(METADATA_PATH, "r", encoding="utf-8") as f:
                    st.session_state.documents = json.load(f)
            # 全ソースを選択状態にする
            st.session_state.selected_sources = {
                d["name"] for d in st.session_state.documents
            }
    except Exception:
        st.warning(
            "保存済みデータの読み込みに失敗しました。\n\n"
            "ソースを再度アップロードしてください。"
        )
        # 破損したストレージを除去して次回起動を正常にする
        if Path(STORAGE_DIR).exists():
            shutil.rmtree(STORAGE_DIR)
            os.makedirs(STORAGE_DIR, exist_ok=True)
            Path(_embed_marker).write_text(EMBED_MODEL, encoding="utf-8")

# チャット履歴の復元（インデックス読み込みとは独立して実行）
if not st.session_state.chat_history and Path(CHAT_HISTORY_PATH).exists():
    try:
        with open(CHAT_HISTORY_PATH, "r", encoding="utf-8") as f:
            st.session_state.chat_history = json.load(f)
    except (json.JSONDecodeError, OSError):
        pass

# selected_sources を documents と同期（stale な名前を除去）
valid_names = {d["name"] for d in st.session_state.documents}
st.session_state.selected_sources &= valid_names


# ---------------------------------------------------------------------------
# ファイル読み込み関数
# ---------------------------------------------------------------------------


def extract_text_from_pdf(file):
    """PDFからテキスト抽出（ページ番号付き）"""
    file.seek(0)
    pdf_reader = PyPDF2.PdfReader(file)
    documents = []
    total_pages = len(pdf_reader.pages)
    for page_num, page in enumerate(pdf_reader.pages, 1):
        text = page.extract_text()
        if text is not None and text.strip():
            documents.append(
                {
                    "text": text,
                    "metadata": {
                        "page": page_num,
                        "total_pages": total_pages,
                    },
                }
            )
    return documents


def extract_text_from_docx(file):
    """DOCXからテキスト抽出"""
    file.seek(0)
    doc = docx.Document(file)
    text = "\n".join(
        [para.text for para in doc.paragraphs if para.text.strip()]
    )
    if not text.strip():
        return []
    return [{"text": text, "metadata": {}}]


def extract_text_from_pptx(file):
    """PPTXからテキスト抽出（スライド番号付き）"""
    file.seek(0)
    prs = Presentation(file)
    documents = []
    total_slides = len(prs.slides)
    for slide_num, slide in enumerate(prs.slides, 1):
        text_parts = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                text_parts.append(shape.text)
        if text_parts:
            documents.append(
                {
                    "text": "\n".join(text_parts),
                    "metadata": {
                        "slide": slide_num,
                        "total_slides": total_slides,
                    },
                }
            )
    return documents


def load_document(uploaded_file):
    """ファイルタイプに応じた読み込み"""
    file_extension = Path(uploaded_file.name).suffix.lower()
    try:
        if file_extension == ".pdf":
            return extract_text_from_pdf(uploaded_file)
        elif file_extension == ".docx":
            return extract_text_from_docx(uploaded_file)
        elif file_extension == ".pptx":
            return extract_text_from_pptx(uploaded_file)
        elif file_extension in (".txt", ".md"):
            uploaded_file.seek(0)
            text = uploaded_file.read().decode("utf-8")
            if not text.strip():
                return []
            return [{"text": text, "metadata": {}}]
        else:
            st.warning(f"未対応のファイル形式です: {file_extension}")
            return None
    except Exception as e:
        st.error(
            f"ファイルの読み込みに失敗しました: {uploaded_file.name}\n\n"
            f"ファイルが破損していないか確認してください。（詳細: {e}）"
        )
        return None


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------


def persist_index_and_metadata():
    """インデックスとメタデータを永続化する"""
    os.makedirs(STORAGE_DIR, exist_ok=True)
    st.session_state.index.storage_context.persist(persist_dir=STORAGE_DIR)
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(
            st.session_state.documents, f, ensure_ascii=False, indent=2
        )


def persist_chat_history():
    """チャット履歴をファイルに永続化する"""
    os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(CHAT_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(
            st.session_state.chat_history, f, ensure_ascii=False, indent=2
        )


def build_query_engine():
    """選択されたソースに基づいてクエリエンジンを構築する。

    Returns:
        クエリエンジン、またはソース未選択時は None
    """
    all_names = {d["name"] for d in st.session_state.documents}
    selected = st.session_state.selected_sources & all_names

    # ソースが1つも選択されていない場合はクエリ不可
    if not selected:
        return None

    # 常にメタデータフィルタを適用
    # （個別削除されたドキュメントのノードがインデックスに残るため）
    if HAS_FILTERS:
        metadata_filters = MetadataFilters(
            filters=[
                MetadataFilter(key="file_name", value=name)
                for name in selected
            ],
            condition=FilterCondition.OR,
        )
        return st.session_state.index.as_query_engine(
            similarity_top_k=3,
            response_mode="compact",
            filters=metadata_filters,
            streaming=True,
        )

    return st.session_state.index.as_query_engine(
        similarity_top_k=3,
        response_mode="compact",
        streaming=True,
    )


def collect_sources(response):
    """レスポンスからソース情報を収集する"""
    sources = []
    if response.source_nodes:
        for node in response.source_nodes:
            score = node.score
            sources.append(
                {
                    "file_name": node.metadata.get("file_name", "unknown"),
                    "file_type": node.metadata.get("file_type", ""),
                    "page": node.metadata.get("page"),
                    "slide": node.metadata.get("slide"),
                    "total_pages": node.metadata.get("total_pages"),
                    "total_slides": node.metadata.get("total_slides"),
                    "score": score if score is not None else 0.0,
                    "text": node.text,
                }
            )
    return sources


def get_last_sources():
    """チャット履歴から最後のソース情報を取得する"""
    for msg in reversed(st.session_state.chat_history):
        if msg.get("sources"):
            return msg["sources"]
    return []


# ---------------------------------------------------------------------------
# サイドバー（ソースパネル）
# ---------------------------------------------------------------------------

with st.sidebar:
    # ヘッダー
    st.markdown("# ソース")

    doc_count = len(st.session_state.documents)
    if doc_count > 0:
        sel_count = len(st.session_state.selected_sources)
        st.markdown(
            f'<span class="source-badge">'
            f"{sel_count}/{doc_count} 件選択中</span>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ファイルアップロード
    uploaded_files = st.file_uploader(
        "ソースを追加",
        type=["pdf", "docx", "pptx", "txt", "md"],
        accept_multiple_files=True,
        help="PDF、Word、PowerPoint、テキストファイルに対応",
        key=f"file_uploader_{st.session_state.uploader_key}",
        label_visibility="collapsed",
    )

    # アップロード処理
    if uploaded_files:
        registered_names = {d["name"] for d in st.session_state.documents}
        new_doc_parts = {}
        no_text_files = []

        with st.spinner("文書を読み込み中..."):
            for uploaded_file in uploaded_files:
                name = uploaded_file.name
                if name in registered_names:
                    continue
                if name in st.session_state.failed_files:
                    continue

                doc_parts = load_document(uploaded_file)

                if doc_parts is None:
                    st.session_state.failed_files.add(name)
                elif len(doc_parts) == 0:
                    no_text_files.append(name)
                    st.session_state.failed_files.add(name)
                else:
                    new_doc_parts[name] = doc_parts

        for name in no_text_files:
            st.warning(
                f"テキストを抽出できませんでした: {name}\n\n"
                "スキャン画像のみのPDF等は対応していません。"
            )

        need_rerun = False
        if new_doc_parts:
            with st.spinner("インデックス構築中..."):
                try:
                    new_documents = []
                    for name, parts in new_doc_parts.items():
                        file_type = Path(name).suffix[1:].upper()
                        for part in parts:
                            metadata = {
                                "file_name": name,
                                "file_type": file_type,
                                **part["metadata"],
                            }
                            new_documents.append(
                                Document(
                                    text=part["text"], metadata=metadata
                                )
                            )

                    if st.session_state.index is None:
                        st.session_state.index = (
                            VectorStoreIndex.from_documents(new_documents)
                        )
                    else:
                        for doc in new_documents:
                            st.session_state.index.insert(doc)

                    for name, parts in new_doc_parts.items():
                        st.session_state.documents.append(
                            {
                                "name": name,
                                "type": Path(name).suffix[1:].upper(),
                                "uploaded_at": datetime.now().isoformat(),
                                "parts": len(parts),
                                "texts": [
                                    {
                                        "text": p["text"],
                                        "metadata": p["metadata"],
                                    }
                                    for p in parts
                                ],
                            }
                        )
                        st.session_state.selected_sources.add(name)

                    persist_index_and_metadata()
                    st.session_state.uploader_key += 1
                    need_rerun = True
                except Exception as e:
                    st.error(f"インデックス構築エラー: {e}")

        # st.rerun() は spinner / try-except の外で呼ぶ
        # （spinner 内で呼ぶと RerunException がコンテキストを壊し接続エラーになる）
        if need_rerun:
            st.rerun()

    # ソース一覧（チェックボックス + 個別削除）
    if st.session_state.documents:
        st.divider()
        st.caption("読み込み済みソース — チェックで参照対象を選択")

        doc_to_remove = None
        for doc in st.session_state.documents:
            icon = ICON_MAP.get(doc["type"], "📄")
            cb_col, del_col = st.columns([5, 1])
            with cb_col:
                is_selected = st.checkbox(
                    f"{icon} {doc['name']}",
                    value=(doc["name"] in st.session_state.selected_sources),
                    key=f"src_{doc['name']}",
                )
                if is_selected:
                    st.session_state.selected_sources.add(doc["name"])
                else:
                    st.session_state.selected_sources.discard(doc["name"])
            with del_col:
                if st.button(
                    "✕",
                    key=f"del_{doc['name']}",
                    help=f"{doc['name']} を削除",
                ):
                    doc_to_remove = doc["name"]

            # ソース内容の閲覧
            texts = doc.get("texts", [])
            if texts:
                with st.expander(
                    f"📖 内容を表示（{doc['parts']}パート）",
                    expanded=False,
                ):
                    for pi, part in enumerate(texts):
                        meta = part.get("metadata", {})
                        page = meta.get("page")
                        slide = meta.get("slide")
                        if page:
                            st.caption(
                                f"ページ {page}"
                                f" / {meta.get('total_pages', '?')}"
                            )
                        elif slide:
                            st.caption(
                                f"スライド {slide}"
                                f" / {meta.get('total_slides', '?')}"
                            )
                        st.text_area(
                            f"part_{pi}",
                            part["text"],
                            height=150,
                            key=f"view_{doc['name']}_{pi}",
                            label_visibility="collapsed",
                            disabled=True,
                        )

        # 個別削除の実行（ループ外で処理）
        if doc_to_remove:
            st.session_state.documents = [
                d
                for d in st.session_state.documents
                if d["name"] != doc_to_remove
            ]
            st.session_state.selected_sources.discard(doc_to_remove)
            st.session_state.failed_files.discard(doc_to_remove)

            if st.session_state.documents:
                # メタデータを更新（インデックス内の孤立ノードはフィルタで除外）
                persist_index_and_metadata()
            else:
                # 全件削除された場合
                st.session_state.index = None
                if Path(STORAGE_DIR).exists():
                    shutil.rmtree(STORAGE_DIR)
            st.rerun()

        st.divider()
        if st.button("🗑️ すべてクリア", use_container_width=True):
            st.session_state.documents = []
            st.session_state.index = None
            st.session_state.chat_history = []
            st.session_state.failed_files = set()
            st.session_state.selected_sources = set()
            st.session_state.uploader_key += 1
            if Path(STORAGE_DIR).exists():
                shutil.rmtree(STORAGE_DIR)
            st.rerun()
        if st.session_state.chat_history and st.button(
            "💬 会話をクリア", use_container_width=True
        ):
            st.session_state.chat_history = []
            if Path(CHAT_HISTORY_PATH).exists():
                os.remove(CHAT_HISTORY_PATH)
            st.rerun()

# ---------------------------------------------------------------------------
# メインエリア
# ---------------------------------------------------------------------------

if st.session_state.index is not None:
    # --- 2カラムレイアウト: チャット | スタジオ ---
    chat_col, studio_col = st.columns([5, 2])

    # ===== スタジオパネル（右） =====
    with studio_col:
        st.markdown(
            '<p class="panel-header">スタジオ</p>',
            unsafe_allow_html=True,
        )

        # アクションボタン
        action_prompts = {
            "📝 要約を生成": (
                "登録されている文書の主要な内容を、"
                "簡潔に要約してください。"
            ),
            "❓ FAQ を作成": (
                "文書に基づいて、想定されるよくある質問（FAQ）と"
                "その回答を作成してください。"
            ),
            "📋 仕様一覧": (
                "製品の主な仕様・スペックを箇条書きでまとめてください。"
            ),
            "🔧 トラブル対応": (
                "よくあるトラブル・エラーとその対処法を"
                "一覧にしてください。"
            ),
        }

        for label, prompt_text in action_prompts.items():
            if st.button(
                label,
                use_container_width=True,
                key=f"act_{label}",
                type="primary",
            ):
                st.session_state.quick_question = prompt_text
                st.session_state.quick_question_label = label

        # 参照元表示（最後の応答から）
        last_sources = get_last_sources()
        if last_sources:
            st.markdown("---")
            st.markdown(
                '<p class="panel-header">参照元</p>',
                unsafe_allow_html=True,
            )
            for i, src in enumerate(last_sources[:5], 1):
                icon = ICON_MAP.get(src.get("file_type", ""), "📄")
                loc = ""
                if src.get("page"):
                    loc = f" - p.{src['page']}"
                elif src.get("slide"):
                    loc = f" - Slide {src['slide']}"
                score = src.get("score")
                score_str = f" ({score:.0%})" if score is not None else ""

                safe_name = html.escape(src["file_name"])
                st.markdown(
                    f'<div class="ref-card">'
                    f'<span class="ref-title">[{i}] {icon} '
                    f"{safe_name}</span><br>"
                    f'<span class="ref-meta">{loc}{score_str}</span>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # ステータス
        st.markdown("---")
        sel = len(st.session_state.selected_sources)
        total = len(st.session_state.documents)
        st.caption(f"📊 {sel}/{total} ソース選択中")
        if st.session_state.chat_history:
            export_history = [
                msg
                for msg in st.session_state.chat_history
                if not msg.get("is_error")
            ]
            if export_history:
                export_data = {
                    "export_date": datetime.now().isoformat(),
                    "conversation": export_history,
                }
                st.download_button(
                    "📥 会話をエクスポート",
                    json.dumps(
                        export_data, ensure_ascii=False, indent=2
                    ),
                    f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    "application/json",
                    use_container_width=True,
                )

    # ===== チャットパネル（左） =====
    with chat_col:
        # チャット履歴表示
        for idx, message in enumerate(st.session_state.chat_history):
            with st.chat_message(message["role"]):
                if message.get("is_error"):
                    st.error(message["content"])
                else:
                    st.markdown(message["content"])

                # インラインソース参照（チャット内に簡潔に表示）
                if message.get("sources"):
                    refs = message["sources"]
                    ref_labels = []
                    for j, src in enumerate(refs, 1):
                        icon = ICON_MAP.get(
                            src.get("file_type", ""), "📄"
                        )
                        ref_labels.append(
                            f"`[{j}]` {icon} {src['file_name']}"
                        )
                    with st.expander(
                        f"📎 {len(refs)}件の参照元", expanded=False
                    ):
                        st.markdown(" | ".join(ref_labels))
                        for j, src in enumerate(refs, 1):
                            st.text_area(
                                f"原文 [{j}]",
                                src.get("text", ""),
                                height=100,
                                key=f"ref_{idx}_{j}",
                                label_visibility="collapsed",
                            )

    # チャット入力（フルwidth - Streamlit の制約）
    prompt = st.chat_input(
        "質問を入力してください...",
    )

    # クイック質問（スタジオアクション）の処理
    # ユーザーがチャット入力に入力済みの場合はそちらを優先する
    studio_label = None
    if "quick_question" in st.session_state:
        if not prompt:
            prompt = st.session_state.quick_question
            studio_label = st.session_state.get("quick_question_label")
        del st.session_state.quick_question
        st.session_state.pop("quick_question_label", None)

    if prompt:
        timestamp = datetime.now().isoformat()

        # チャットに表示するテキスト（スタジオ操作はラベル、手入力はそのまま）
        display_text = studio_label if studio_label else prompt

        st.session_state.chat_history.append(
            {
                "role": "user",
                "content": display_text,
                "timestamp": timestamp,
                "query": prompt,
            }
        )

        # ユーザーの操作を即座に表示
        with chat_col:
            with st.chat_message("user"):
                st.markdown(display_text)

        # クエリ実行
        try:
            query_engine = build_query_engine()
            if query_engine is None:
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": "ソースが選択されていません。\n\n"
                        "サイドバーで少なくとも1つのソースを"
                        "チェックしてください。",
                        "is_error": True,
                        "sources": [],
                        "timestamp": timestamp,
                    }
                )
            else:
                with chat_col:
                    with st.chat_message("assistant"):
                        with st.spinner("回答を作成中..."):
                            response = query_engine.query(prompt)
                        # ストリーミング: トークンをリアルタイム表示
                        answer_text = st.write_stream(
                            response.response_gen
                        )

                sources = collect_sources(response)

                if not answer_text:
                    answer_text = (
                        "回答を生成できませんでした。\n\n"
                        "質問の表現を変えるか、別のソースを追加してみてください。"
                    )

                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": answer_text,
                        "sources": sources,
                        "timestamp": timestamp,
                    }
                )
        except Exception as e:
            error_detail = str(e)
            if "refused" in error_detail.lower() or "connect" in error_detail.lower():
                error_msg = (
                    "Ollama に接続できません。\n\n"
                    "**確認事項:**\n"
                    "1. Ollama が起動しているか\n"
                    "2. `ollama serve` をコマンドプロンプトで実行\n\n"
                    f"詳細: `{error_detail}`"
                )
            elif "model" in error_detail.lower() or "not found" in error_detail.lower():
                error_msg = (
                    "LLMモデルが見つかりません。\n\n"
                    "コマンドプロンプトで以下を実行してください:\n"
                    f"```\nollama pull {OLLAMA_MODEL}\n```\n\n"
                    f"詳細: `{error_detail}`"
                )
            else:
                error_msg = (
                    "回答の生成中にエラーが発生しました。\n\n"
                    f"詳細: `{error_detail}`"
                )
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": error_msg,
                    "is_error": True,
                    "sources": [],
                    "timestamp": timestamp,
                }
            )

        try:
            persist_chat_history()
        except OSError:
            pass
        st.rerun()

else:
    # --- インデックス未構築時のウェルカム画面 ---
    st.markdown("")
    st.markdown("")

    welcome_col1, welcome_col2, welcome_col3 = st.columns([1, 2, 1])
    with welcome_col2:
        st.markdown(
            """
            <div style="text-align: center; padding: 60px 20px;">
                <h1 style="color: #1a73e8; font-size: 2.5rem;">🔬</h1>
                <h2 style="color: #1f1f1f;">NB Tech Sys</h2>
                <p style="color: #5f6368; font-size: 1.1rem;">
                    技術文書をアップロードして、AIに質問しましょう
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### 使い方")
        st.markdown(
            """
1. **サイドバーからソースを追加** — PDF、Word、PowerPoint、テキスト、Markdown
2. **チェックボックスで対象を選択** — 質問に使うソースを絞り込み
3. **チャットで質問** — 製品仕様、操作手順、トラブル対処など
4. **スタジオで一括生成** — 要約、FAQ、仕様一覧をワンクリック
"""
        )

        st.markdown("#### 対応フォーマット")
        fmt_col1, fmt_col2, fmt_col3, fmt_col4, fmt_col5 = st.columns(5)
        with fmt_col1:
            st.markdown("📕 **PDF**\n\n取扱説明書")
        with fmt_col2:
            st.markdown("📊 **PPTX**\n\nセミナー資料")
        with fmt_col3:
            st.markdown("📘 **DOCX**\n\n技術ノート")
        with fmt_col4:
            st.markdown("📄 **TXT**\n\nテキスト資料")
        with fmt_col5:
            st.markdown("📝 **MD**\n\nMarkdown")
