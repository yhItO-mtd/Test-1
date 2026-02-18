# technical_support_rag.py
"""
NB_Tech_Sys - 技術サポートRAGシステム
取扱説明書・セミナー資料からの自動回答システム
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
import json
import shutil
import os
from datetime import datetime

# ページ設定
st.set_page_config(
    page_title="技術サポート AI",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# セッション状態初期化
if "index" not in st.session_state:
    st.session_state.index = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "documents" not in st.session_state:
    st.session_state.documents = []

STORAGE_DIR = "./storage"
METADATA_PATH = os.path.join(STORAGE_DIR, "metadata.json")


# モデル設定
@st.cache_resource
def setup_models():
    """埋め込みモデルとLLMを初期化する"""
    Settings.embed_model = HuggingFaceEmbedding(
        model_name="intfloat/multilingual-e5-large",
        cache_folder="./models",
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


setup_models()


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
                    "metadata": {"page": page_num, "total_pages": total_pages},
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
    """ファイルタイプに応じた読み込み。常に seek(0) してから読む。"""
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
        st.error(f"ファイル読み込みエラー ({uploaded_file.name}): {e}")
        return None


# ---------------------------------------------------------------------------
# ソース表示ヘルパー
# ---------------------------------------------------------------------------


def display_sources(sources, key_prefix, expanded=False):
    """検索結果のソース情報を表示する共通関数"""
    if not sources:
        return
    with st.expander("📎 参照元の詳細", expanded=expanded):
        for i, source in enumerate(sources, 1):
            st.markdown(f"### [{i}] {source['file_name']}")

            if source.get("page"):
                total = source.get("total_pages", "?")
                st.info(f"📄 ページ {source['page']}/{total}")
            elif source.get("slide"):
                total = source.get("total_slides", "?")
                st.info(f"📊 スライド {source['slide']}/{total}")

            score = source.get("score")
            if score is not None:
                st.caption(f"関連度: {score:.1%}")

            st.markdown("**参照した文章（原文）：**")
            st.text_area(
                f"原文_{i}",
                source.get("text", ""),
                height=150,
                key=f"source_{key_prefix}_{i}",
                label_visibility="collapsed",
            )
            st.divider()


# ---------------------------------------------------------------------------
# 永続化ヘルパー
# ---------------------------------------------------------------------------


def persist_index_and_metadata():
    """インデックスとメタデータを永続化する"""
    os.makedirs(STORAGE_DIR, exist_ok=True)
    st.session_state.index.storage_context.persist(persist_dir=STORAGE_DIR)
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(st.session_state.documents, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# サイドバー
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("📚 ナレッジベース管理")

    # 既存インデックスの読み込み
    if Path(STORAGE_DIR).exists() and st.session_state.index is None:
        if st.button("💾 保存済みデータを読み込む"):
            with st.spinner("読み込み中..."):
                try:
                    storage_context = StorageContext.from_defaults(
                        persist_dir=STORAGE_DIR
                    )
                    st.session_state.index = load_index_from_storage(
                        storage_context
                    )
                    if Path(METADATA_PATH).exists():
                        with open(METADATA_PATH, "r", encoding="utf-8") as f:
                            st.session_state.documents = json.load(f)
                    st.success("読み込み完了！")
                except Exception as e:
                    st.error(f"読み込みエラー: {e}")

    st.divider()

    # ファイルアップロード
    uploaded_files = st.file_uploader(
        "文書をアップロード",
        type=["pdf", "docx", "pptx", "txt"],
        accept_multiple_files=True,
        help="取扱説明書、セミナー資料、アプリケーションノート等",
    )

    if uploaded_files:
        # 新規文書を抽出（パース結果をキャッシュし、二重読み込みを防ぐ）
        registered_names = {d["name"] for d in st.session_state.documents}
        new_doc_parts = {}  # filename -> list of doc parts

        for uploaded_file in uploaded_files:
            if uploaded_file.name not in registered_names:
                doc_parts = load_document(uploaded_file)
                if doc_parts:
                    new_doc_parts[uploaded_file.name] = doc_parts

        # インデックスの構築 / 更新
        # NOTE: documents リストはインデックス構築成功後に更新する
        #       （失敗時に「登録済みだがインデックス未構築」の不整合を防ぐ）
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
                                Document(text=part["text"], metadata=metadata)
                            )

                    if st.session_state.index is None:
                        st.session_state.index = (
                            VectorStoreIndex.from_documents(new_documents)
                        )
                    else:
                        for doc in new_documents:
                            st.session_state.index.insert(doc)

                    # インデックス構築成功後にメタデータを更新
                    for name, parts in new_doc_parts.items():
                        st.session_state.documents.append(
                            {
                                "name": name,
                                "type": Path(name).suffix[1:].upper(),
                                "uploaded_at": datetime.now().isoformat(),
                                "parts": len(parts),
                            }
                        )

                    persist_index_and_metadata()
                    st.success(
                        f"✅ {len(new_doc_parts)}件の新規文書を登録"
                        f"（合計: {len(st.session_state.documents)}件）"
                    )
                except Exception as e:
                    st.error(f"インデックス構築エラー: {e}")

    # 登録文書一覧
    if st.session_state.documents:
        st.subheader("📂 登録済み文書")
        icon_map = {
            "PDF": "📕",
            "DOCX": "📘",
            "PPTX": "📊",
            "TXT": "📄",
        }
        for doc in st.session_state.documents:
            icon = icon_map.get(doc["type"], "📄")
            st.text(f"{icon} {doc['name']}")
            if "parts" in doc:
                st.caption(f"   {doc['parts']}セクション")

        st.divider()

        if st.button("🗑️ すべてクリア", type="secondary"):
            st.session_state.documents = []
            st.session_state.index = None
            st.session_state.chat_history = []
            if Path(STORAGE_DIR).exists():
                shutil.rmtree(STORAGE_DIR)
            st.rerun()

# ---------------------------------------------------------------------------
# メインエリア
# ---------------------------------------------------------------------------

st.title("🔬 技術サポート AI")
st.caption("取扱説明書・セミナー資料から自動回答")

# チャット履歴表示
for idx, message in enumerate(st.session_state.chat_history):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            display_sources(message["sources"], f"hist_{idx}")

# チャット入力
if st.session_state.index is not None:
    # クイック質問
    st.markdown("### 💡 よくある質問")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📐 仕様・スペック"):
            st.session_state.quick_question = (
                "この製品の主な仕様とスペックを教えてください"
            )
    with col2:
        if st.button("⚠️ トラブルシューティング"):
            st.session_state.quick_question = (
                "よくあるトラブルとその対処法を教えてください"
            )
    with col3:
        if st.button("🔧 メンテナンス"):
            st.session_state.quick_question = (
                "日常的なメンテナンス方法を教えてください"
            )

    # 実際の質問入力
    prompt = st.chat_input(
        "質問を入力してください（例：ベースライン補正の手順は？）"
    )

    # クイック質問の処理
    if "quick_question" in st.session_state:
        prompt = st.session_state.quick_question
        del st.session_state.quick_question

    if prompt:
        timestamp = datetime.now().isoformat()

        # ユーザーメッセージ
        st.session_state.chat_history.append(
            {"role": "user", "content": prompt, "timestamp": timestamp}
        )
        with st.chat_message("user"):
            st.markdown(prompt)

        # AI応答
        with st.chat_message("assistant"):
            with st.spinner("文書を検索中..."):
                try:
                    query_engine = st.session_state.index.as_query_engine(
                        similarity_top_k=5,
                        response_mode="compact",
                    )
                    response = query_engine.query(prompt)

                    st.markdown(response.response)

                    # ソース情報収集
                    sources = []
                    if response.source_nodes:
                        for node in response.source_nodes:
                            score = node.score
                            sources.append(
                                {
                                    "file_name": node.metadata.get(
                                        "file_name", "unknown"
                                    ),
                                    "file_type": node.metadata.get(
                                        "file_type", ""
                                    ),
                                    "page": node.metadata.get("page"),
                                    "slide": node.metadata.get("slide"),
                                    "total_pages": node.metadata.get(
                                        "total_pages"
                                    ),
                                    "total_slides": node.metadata.get(
                                        "total_slides"
                                    ),
                                    "score": score
                                    if score is not None
                                    else 0.0,
                                    "text": node.text,
                                }
                            )

                    if sources:
                        display_sources(
                            sources, f"new_{timestamp}", expanded=True
                        )

                    # 履歴に追加
                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": response.response,
                            "sources": sources,
                            "timestamp": timestamp,
                        }
                    )
                except Exception as e:
                    error_msg = (
                        f"回答の生成中にエラーが発生しました: {e}\n\n"
                        "Ollama が起動しているか確認してください。"
                    )
                    st.error(error_msg)
                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": error_msg,
                            "sources": [],
                            "timestamp": timestamp,
                        }
                    )

else:
    st.info(
        "👈 サイドバーから取扱説明書やセミナー資料をアップロードしてください"
    )

    st.markdown(
        """
    ### 使い方

    1. **文書をアップロード**: PDF、Word、PowerPoint形式の技術文書
    2. **質問を入力**: 製品仕様、操作方法、トラブル対処など
    3. **回答を確認**: 参照元の原文も確認できます

    ### 対応文書
    - 📕 取扱説明書（PDF）
    - 📊 セミナー資料（PPTX）
    - 📘 アプリケーションノート（Word/PDF）
    - 📄 技術資料（TXT）
    """
    )

# ---------------------------------------------------------------------------
# フッター
# ---------------------------------------------------------------------------

st.divider()
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("💬 会話履歴クリア"):
        st.session_state.chat_history = []
        st.rerun()

with col2:
    if st.session_state.chat_history:
        export_data = {
            "export_date": datetime.now().isoformat(),
            "conversation": st.session_state.chat_history,
        }
        st.download_button(
            "📥 会話をエクスポート",
            json.dumps(export_data, ensure_ascii=False, indent=2),
            f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "application/json",
        )

with col3:
    if st.session_state.index:
        st.success("✅ 準備完了")
    else:
        st.warning("⏳ 文書待機中")

with col4:
    st.caption(f"📊 登録: {len(st.session_state.documents)}件")
