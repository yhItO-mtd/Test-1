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
}


# ---------------------------------------------------------------------------
# モデル設定
# ---------------------------------------------------------------------------


@st.cache_resource
def setup_models():
    """埋め込みモデルとLLMを初期化する"""
    Settings.embed_model = HuggingFaceEmbedding(
        model_name="intfloat/multilingual-e5-large",
        cache_folder=MODELS_DIR,
    )
    Settings.llm = Ollama(
        model="llama3.1:8b",
        request_timeout=300.0,
        temperature=0.0,
        system_prompt=(
            "あなたは製品の技術サポート専門AIです。\n"
            "以下のルールに従ってください：\n"
            "1. 提供された文書の情報のみを使用する\n"
            "2. 不明な場合は「文書に記載がありません」と回答\n"
            "3. 具体的なページ番号や章を引用する\n"
            "4. 技術用語は正確に使用する\n"
            "5. 簡潔で分かりやすく回答する"
        ),
    )
    return True


with st.spinner("AIモデルを初期化中...（初回は数分かかります）"):
    setup_models()

# 保存済みインデックスの自動読み込み
if st.session_state.index is None and Path(STORAGE_DIR).exists():
    try:
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
        pass

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
        elif file_extension == ".txt":
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

    # 全ソース選択時はフィルタなし
    if HAS_FILTERS and selected != all_names:
        metadata_filters = MetadataFilters(
            filters=[
                MetadataFilter(key="file_name", value=name)
                for name in selected
            ],
            condition=FilterCondition.OR,
        )
        return st.session_state.index.as_query_engine(
            similarity_top_k=5,
            response_mode="compact",
            filters=metadata_filters,
        )

    return st.session_state.index.as_query_engine(
        similarity_top_k=5,
        response_mode="compact",
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
        type=["pdf", "docx", "pptx", "txt"],
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
                            }
                        )
                        st.session_state.selected_sources.add(name)

                    persist_index_and_metadata()
                    st.success(f"✅ {len(new_doc_parts)}件追加")
                except Exception as e:
                    st.error(f"インデックス構築エラー: {e}")

    # ソース一覧（チェックボックス付き）
    if st.session_state.documents:
        st.divider()

        for doc in st.session_state.documents:
            icon = ICON_MAP.get(doc["type"], "📄")
            is_selected = st.checkbox(
                f"{icon} {doc['name']}",
                value=(doc["name"] in st.session_state.selected_sources),
                key=f"src_{doc['name']}",
            )
            if is_selected:
                st.session_state.selected_sources.add(doc["name"])
            else:
                st.session_state.selected_sources.discard(doc["name"])

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
            "📝 要約を生成": "登録されている文書の主要な内容を簡潔に要約してください。",
            "❓ FAQ を作成": (
                "文書に基づいて、想定されるよくある質問（FAQ）と"
                "その回答を5つ作成してください。"
            ),
            "📋 仕様一覧": "製品の主な仕様・スペックを箇条書きでまとめてください。",
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
    if "quick_question" in st.session_state:
        if not prompt:
            prompt = st.session_state.quick_question
        del st.session_state.quick_question

    if prompt:
        timestamp = datetime.now().isoformat()

        st.session_state.chat_history.append(
            {"role": "user", "content": prompt, "timestamp": timestamp}
        )

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
                response = query_engine.query(prompt)
                sources = collect_sources(response)

                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": response.response,
                        "sources": sources,
                        "timestamp": timestamp,
                    }
                )
        except Exception:
            error_msg = (
                "回答の生成中にエラーが発生しました。\n\n"
                "Ollama が起動しているか確認してください。"
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
1. **サイドバーからソースを追加** — PDF、Word、PowerPoint、テキスト
2. **チェックボックスで対象を選択** — 質問に使うソースを絞り込み
3. **チャットで質問** — 製品仕様、操作手順、トラブル対処など
4. **スタジオで一括生成** — 要約、FAQ、仕様一覧をワンクリック
"""
        )

        st.markdown("#### 対応フォーマット")
        fmt_col1, fmt_col2, fmt_col3, fmt_col4 = st.columns(4)
        with fmt_col1:
            st.markdown("📕 **PDF**\n\n取扱説明書")
        with fmt_col2:
            st.markdown("📊 **PPTX**\n\nセミナー資料")
        with fmt_col3:
            st.markdown("📘 **DOCX**\n\n技術ノート")
        with fmt_col4:
            st.markdown("📄 **TXT**\n\nテキスト資料")
