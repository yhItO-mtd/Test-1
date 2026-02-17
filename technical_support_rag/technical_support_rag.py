# technical_support_rag.py
"""
Technical Support RAG System - Streamlit Application

PDF documents (including scanned / image-based) are uploaded, indexed with
LlamaIndex, and queried via a local Ollama LLM. All processing runs offline.

OCR pipeline:
  PyMuPDF (fitz)  -- extract embedded text per page
  pytesseract     -- OCR for pages where extracted text is too short
  Pillow          -- image handling between fitz and tesseract
"""
import shutil
import json
from datetime import datetime
from io import BytesIO
from pathlib import Path

import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
from llama_index.core import (
    VectorStoreIndex,
    Document,
    Settings,
    StorageContext,
    load_index_from_storage,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama

# ---------------------------------------------------------------------------
# OCR availability check
# ---------------------------------------------------------------------------
try:
    import pytesseract

    # Quick sanity check – will raise if the tesseract binary is missing
    pytesseract.get_tesseract_version()
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Technical Support AI",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

STORAGE_DIR = Path("./storage")
METADATA_FILE = STORAGE_DIR / "metadata.json"

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "index" not in st.session_state:
    st.session_state.index = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "documents" not in st.session_state:
    st.session_state.documents = []
# Cache extracted document parts so we never lose them across Streamlit reruns
if "doc_parts_cache" not in st.session_state:
    st.session_state.doc_parts_cache = {}  # filename -> list of part dicts
if "ocr_enabled" not in st.session_state:
    st.session_state.ocr_enabled = OCR_AVAILABLE

# ---------------------------------------------------------------------------
# Model setup
# ---------------------------------------------------------------------------

# Ollama models suitable for bilingual (Japanese + English) technical support.
# The dict value is a short description shown in the UI.
AVAILABLE_MODELS: dict[str, str] = {
    "qwen2.5:7b": "Qwen 2.5 7B — 日英バランス型（推奨・VRAM 5GB）",
    "qwen2.5:14b": "Qwen 2.5 14B — 高精度（VRAM 10GB）",
    "gemma2:9b": "Gemma 2 9B — 多言語対応（VRAM 7GB）",
    "llama3.1:8b": "Llama 3.1 8B — 英語中心（日本語は弱い）",
}

DEFAULT_MODEL = "qwen2.5:7b"

if "selected_model" not in st.session_state:
    st.session_state.selected_model = DEFAULT_MODEL

SYSTEM_PROMPT = (
    "You are a technical support AI specialised in product documentation.\n"
    "Follow these rules:\n"
    "1. Use ONLY information from the provided documents.\n"
    "2. If the answer is not in the documents, say so clearly.\n"
    "3. Cite specific page numbers or sections.\n"
    "4. Use technical terms accurately.\n"
    "5. Reply in the same language as the user's question "
    "(Japanese or English).\n\n"
    "あなたは製品ドキュメント専門の技術サポートAIです。\n"
    "以下のルールに従ってください：\n"
    "1. 提供された文書の情報のみを使用する\n"
    "2. 不明な場合は「文書に記載がありません」と明示する\n"
    "3. 具体的なページ番号や章を引用する\n"
    "4. 技術用語は正確に使用する\n"
    "5. ユーザーの質問と同じ言語（日本語または英語）で回答する"
)


@st.cache_resource
def setup_embedding():
    """Initialise embedding model (cached, model-independent)."""
    Settings.embed_model = HuggingFaceEmbedding(
        model_name="intfloat/multilingual-e5-large",
        cache_folder="./models",
    )
    return True


@st.cache_resource
def setup_llm(model_name: str):
    """Initialise the Ollama LLM for *model_name* (cached per model)."""
    llm = Ollama(
        model=model_name,
        request_timeout=300.0,
        temperature=0.0,
        system_prompt=SYSTEM_PROMPT,
    )
    Settings.llm = llm
    return llm


try:
    setup_embedding()
    setup_llm(st.session_state.selected_model)
    _models_ok = True
except Exception as exc:
    _models_ok = False
    st.error(f"モデル初期化エラー: {exc}")

# ---------------------------------------------------------------------------
# PDF extraction helpers (PyMuPDF + optional OCR)
# ---------------------------------------------------------------------------

# Minimum number of characters on a page before we consider OCR.
# Pages with fewer characters than this are likely scanned images.
_OCR_CHAR_THRESHOLD = 30

# DPI used when rendering a PDF page to an image for OCR.
_OCR_DPI = 300


def _ocr_page_image(page: fitz.Page) -> str:
    """Render a PDF page to an image and run Tesseract OCR on it."""
    # Render at high DPI for better OCR accuracy
    zoom = _OCR_DPI / 72  # 72 is the default PDF DPI
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    img = Image.open(BytesIO(pix.tobytes("png")))
    text = pytesseract.image_to_string(img, lang="jpn+eng")
    return text


def extract_text_from_pdf(
    file,
    *,
    use_ocr: bool = False,
    progress_callback=None,
) -> list[dict]:
    """Extract per-page text from a PDF using PyMuPDF.

    If *use_ocr* is True and Tesseract is available, pages whose embedded text
    is shorter than ``_OCR_CHAR_THRESHOLD`` characters are OCR-ed automatically.
    A *progress_callback(current, total)* can be supplied for UI feedback.
    """
    pdf_bytes = file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    documents: list[dict] = []

    for page_idx in range(total_pages):
        page = doc[page_idx]
        page_num = page_idx + 1

        # --- embedded text extraction (fast) ---
        text = page.get_text("text")
        extraction_method = "text"

        # --- OCR fallback for image-heavy / scanned pages ---
        if (
            use_ocr
            and OCR_AVAILABLE
            and len(text.strip()) < _OCR_CHAR_THRESHOLD
        ):
            try:
                ocr_text = _ocr_page_image(page)
                if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
                    extraction_method = "ocr"
            except Exception:
                pass  # keep the (possibly empty) embedded text

        if progress_callback is not None:
            progress_callback(page_num, total_pages)

        if text and text.strip():
            documents.append(
                {
                    "text": text,
                    "metadata": {
                        "page": page_num,
                        "total_pages": total_pages,
                        "extraction_method": extraction_method,
                    },
                }
            )

    doc.close()
    return documents


def load_document(uploaded_file, *, use_ocr: bool = False, progress_callback=None) -> list[dict] | None:
    """Load a PDF (or plain-text) file and return extracted parts."""
    ext = Path(uploaded_file.name).suffix.lower()
    try:
        if ext == ".pdf":
            return extract_text_from_pdf(
                uploaded_file,
                use_ocr=use_ocr,
                progress_callback=progress_callback,
            )
        elif ext == ".txt":
            text = uploaded_file.read().decode("utf-8")
            if not text.strip():
                return []
            return [{"text": text, "metadata": {}}]
        else:
            st.warning(f"未対応のファイル形式: {ext}")
            return None
    except Exception as e:
        st.error(f"ファイル読み込みエラー ({uploaded_file.name}): {e}")
        return None

# ---------------------------------------------------------------------------
# Index helpers
# ---------------------------------------------------------------------------

def _build_index_from_cache() -> VectorStoreIndex | None:
    """Build a LlamaIndex VectorStoreIndex from the session doc_parts_cache."""
    all_documents: list[Document] = []
    for filename, parts in st.session_state.doc_parts_cache.items():
        # Find file_type from documents metadata
        file_type = ""
        for d in st.session_state.documents:
            if d["name"] == filename:
                file_type = d["type"]
                break

        for part in parts:
            metadata = {
                "file_name": filename,
                "file_type": file_type,
                **part["metadata"],
            }
            all_documents.append(Document(text=part["text"], metadata=metadata))

    if not all_documents:
        return None

    index = VectorStoreIndex.from_documents(all_documents)

    # Persist
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    index.storage_context.persist(persist_dir=str(STORAGE_DIR))
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.documents, f, ensure_ascii=False, indent=2)

    return index

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("ナレッジベース管理")

    # --- OCR settings ---------------------------------------------------
    if OCR_AVAILABLE:
        st.session_state.ocr_enabled = st.checkbox(
            "OCR を有効にする（スキャンPDF対応）",
            value=st.session_state.ocr_enabled,
            help="テキストが埋め込まれていないスキャン画像ページを自動認識し、OCRでテキスト化します",
        )
    else:
        st.warning(
            "Tesseract が見つかりません。OCR は無効です。\n\n"
            "スキャンPDFに対応するには Tesseract をインストールしてください。"
        )
        st.session_state.ocr_enabled = False

    st.divider()

    # --- LLM model selection --------------------------------------------
    st.subheader("LLM モデル")
    model_labels = [f"{k}  ({v})" for k, v in AVAILABLE_MODELS.items()]
    model_keys = list(AVAILABLE_MODELS.keys())
    current_idx = (
        model_keys.index(st.session_state.selected_model)
        if st.session_state.selected_model in model_keys
        else 0
    )
    chosen_label = st.selectbox(
        "使用モデル",
        model_labels,
        index=current_idx,
        help="ollama pull <モデル名> でダウンロード済みのモデルを選択してください",
    )
    chosen_model = model_keys[model_labels.index(chosen_label)]

    if chosen_model != st.session_state.selected_model:
        st.session_state.selected_model = chosen_model
        # Re-initialise LLM with the new model
        try:
            setup_llm(chosen_model)
            st.success(f"モデルを {chosen_model} に切り替えました")
        except Exception as exc:
            st.error(f"モデル切替エラー: {exc}")

    st.divider()

    # --- Load persisted index -------------------------------------------
    if STORAGE_DIR.exists() and st.session_state.index is None:
        if st.button("保存済みデータを読み込む"):
            with st.spinner("読み込み中..."):
                try:
                    storage_context = StorageContext.from_defaults(
                        persist_dir=str(STORAGE_DIR)
                    )
                    st.session_state.index = load_index_from_storage(storage_context)
                    if METADATA_FILE.exists():
                        with open(METADATA_FILE, "r", encoding="utf-8") as f:
                            st.session_state.documents = json.load(f)
                    st.success("読み込み完了")
                except Exception as exc:
                    st.error(f"読み込みエラー: {exc}")

    st.divider()

    # --- File uploader --------------------------------------------------
    uploaded_files = st.file_uploader(
        "PDF文書をアップロード",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        help="取扱説明書、セミナー資料、アプリケーションノート等（PDF推奨）",
    )

    if uploaded_files:
        new_docs_added = False

        for uploaded_file in uploaded_files:
            fname = uploaded_file.name
            if fname in st.session_state.doc_parts_cache:
                continue

            uploaded_file.seek(0)

            # Progress bar for PDF extraction (OCR can be slow)
            progress_placeholder = st.empty()
            status_placeholder = st.empty()

            def _progress(current: int, total: int):
                progress_placeholder.progress(
                    current / total,
                    text=f"読み取り中: {fname} ({current}/{total} ページ)",
                )

            use_ocr = st.session_state.ocr_enabled
            if use_ocr and Path(fname).suffix.lower() == ".pdf":
                status_placeholder.info(f"OCR有効で処理中: {fname}")

            doc_parts = load_document(
                uploaded_file,
                use_ocr=use_ocr,
                progress_callback=_progress if Path(fname).suffix.lower() == ".pdf" else None,
            )

            progress_placeholder.empty()
            status_placeholder.empty()

            if doc_parts:
                # Count how many pages used OCR
                ocr_pages = sum(
                    1 for p in doc_parts if p["metadata"].get("extraction_method") == "ocr"
                )
                st.session_state.doc_parts_cache[fname] = doc_parts
                st.session_state.documents.append(
                    {
                        "name": fname,
                        "type": Path(fname).suffix[1:].upper(),
                        "uploaded_at": datetime.now().isoformat(),
                        "parts": len(doc_parts),
                        "ocr_pages": ocr_pages,
                    }
                )
                new_docs_added = True

        if new_docs_added or st.session_state.index is None:
            with st.spinner("インデックス構築中..."):
                idx = _build_index_from_cache()
                if idx is not None:
                    st.session_state.index = idx
                    st.success(f"{len(st.session_state.documents)}件の文書を登録")

    # --- Registered documents -------------------------------------------
    if st.session_state.documents:
        st.subheader("登録済み文書")
        _icons = {"PDF": "📕", "TXT": "📄"}
        for doc in st.session_state.documents:
            icon = _icons.get(doc["type"], "📄")
            st.text(f"{icon} {doc['name']}")
            parts_label = f"   {doc['parts']}ページ"
            ocr_count = doc.get("ocr_pages", 0)
            if ocr_count > 0:
                parts_label += f"（うちOCR: {ocr_count}ページ）"
            st.caption(parts_label)

        st.divider()

        if st.button("すべてクリア", type="secondary"):
            st.session_state.documents = []
            st.session_state.index = None
            st.session_state.chat_history = []
            st.session_state.doc_parts_cache = {}
            if STORAGE_DIR.exists():
                shutil.rmtree(STORAGE_DIR)
            st.rerun()

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.title("Technical Support AI")
st.caption("取扱説明書・セミナー資料から自動回答")

# Chat history
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message.get("sources"):
            with st.expander("参照元の詳細", expanded=False):
                for i, source in enumerate(message["sources"], 1):
                    st.markdown(f"**[{i}] {source['file_name']}**")
                    if source.get("page"):
                        method = source.get("extraction_method", "text")
                        method_label = " [OCR]" if method == "ocr" else ""
                        st.info(
                            f"ページ {source['page']}/{source.get('total_pages', '?')}{method_label}"
                        )
                    if source.get("score") is not None:
                        st.caption(f"関連度: {source['score']:.3f}")
                    st.markdown("**参照した文章（原文）：**")
                    st.text_area(
                        f"原文_{i}",
                        source["text"],
                        height=150,
                        key=f"source_{message.get('timestamp', '')}_{i}",
                        label_visibility="collapsed",
                    )
                    st.divider()

# Query input
if st.session_state.index is not None:
    st.markdown("### よくある質問")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("仕様・スペック"):
            st.session_state.quick_question = (
                "この製品の主な仕様とスペックを教えてください"
            )
    with col2:
        if st.button("トラブルシューティング"):
            st.session_state.quick_question = (
                "よくあるトラブルとその対処法を教えてください"
            )
    with col3:
        if st.button("メンテナンス"):
            st.session_state.quick_question = (
                "日常的なメンテナンス方法を教えてください"
            )

    prompt = st.chat_input("質問を入力してください（例：ベースライン補正の手順は？）")

    if "quick_question" in st.session_state:
        prompt = st.session_state.quick_question
        del st.session_state.quick_question

    if prompt:
        timestamp = datetime.now().isoformat()

        st.session_state.chat_history.append(
            {"role": "user", "content": prompt, "timestamp": timestamp}
        )
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("文書を検索中..."):
                try:
                    query_engine = st.session_state.index.as_query_engine(
                        similarity_top_k=5,
                        response_mode="compact",
                    )
                    response = query_engine.query(prompt)
                except Exception as exc:
                    st.error(
                        f"回答生成エラー: {exc}\n\n"
                        "Ollamaが起動しているか確認してください: `ollama serve`"
                    )
                    st.stop()

                st.markdown(response.response)

                sources: list[dict] = []
                for node in response.source_nodes:
                    sources.append(
                        {
                            "file_name": node.metadata.get("file_name", "unknown"),
                            "file_type": node.metadata.get("file_type", ""),
                            "page": node.metadata.get("page"),
                            "total_pages": node.metadata.get("total_pages"),
                            "extraction_method": node.metadata.get("extraction_method", "text"),
                            "score": node.score,
                            "text": node.text,
                        }
                    )

                if sources:
                    with st.expander("参照元の詳細", expanded=True):
                        for i, source in enumerate(sources, 1):
                            st.markdown(f"**[{i}] {source['file_name']}**")
                            if source.get("page"):
                                method = source.get("extraction_method", "text")
                                method_label = " [OCR]" if method == "ocr" else ""
                                st.info(
                                    f"ページ {source['page']}/{source.get('total_pages', '?')}{method_label}"
                                )
                            if source.get("score") is not None:
                                st.caption(f"関連度: {source['score']:.3f}")
                            st.markdown("**参照した文章（原文）：**")
                            st.text_area(
                                f"原文_{i}",
                                source["text"],
                                height=150,
                                key=f"source_new_{timestamp}_{i}",
                                label_visibility="collapsed",
                            )
                            st.divider()

                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": response.response,
                        "sources": sources,
                        "timestamp": timestamp,
                    }
                )
else:
    st.info("サイドバーから取扱説明書やセミナー資料をアップロードしてください")

    st.markdown(
        f"""
### 使い方

1. **PDFをアップロード**: サイドバーから取扱説明書や技術資料を登録
2. **質問を入力**: 製品仕様、操作方法、トラブル対処など
3. **回答を確認**: 参照元のページ番号・原文も確認できます

### 対応ファイル
- 📕 PDF（テキスト埋め込み / スキャン画像どちらも対応）
- 📄 テキストファイル（TXT）

### OCR 状態
- Tesseract: **{"利用可能" if OCR_AVAILABLE else "未インストール"}**
{("- スキャンPDFや画像ベースのPDFも自動でテキスト化されます" if OCR_AVAILABLE else "- スキャンPDFに対応するには [Tesseract](https://github.com/tesseract-ocr/tesseract) をインストールしてください")}
"""
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("会話履歴クリア"):
        st.session_state.chat_history = []
        st.rerun()

with col2:
    if st.session_state.chat_history:
        export_data = {
            "export_date": datetime.now().isoformat(),
            "conversation": st.session_state.chat_history,
        }
        st.download_button(
            "会話をエクスポート",
            json.dumps(export_data, ensure_ascii=False, indent=2),
            f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "application/json",
        )

with col3:
    if st.session_state.index:
        st.success("準備完了")
    else:
        st.warning("文書待機中")

with col4:
    st.caption(f"登録: {len(st.session_state.documents)}件")
