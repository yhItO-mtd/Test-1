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
import html
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
CHAT_HISTORY_FILE = STORAGE_DIR / "chat_history.json"

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
# Two-phase query: store the pending question so the UI can show
# the user message first, then generate the answer on the next rerun.
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None
# Whether to offer restoring saved chat history on startup
if "chat_history_offer" not in st.session_state:
    st.session_state.chat_history_offer = False

# ---------------------------------------------------------------------------
# Model setup
# ---------------------------------------------------------------------------

# Ollama models suitable for bilingual (Japanese + English) technical support.
# Sized for CPU-only environments — larger models are too slow without a GPU.
AVAILABLE_MODELS: dict[str, str] = {
    "qwen2.5:3b": "Qwen 2.5 3B — CPU推奨・日英対応（RAM 4GB・約2GB）",
    "qwen2.5:7b": "Qwen 2.5 7B — 高品質・CPU可（RAM 8GB・約4.7GB）",
    "gemma2:2b": "Gemma 2 2B — 最軽量・多言語（RAM 3GB・約1.6GB）",
    "llama3.2:3b": "Llama 3.2 3B — 英語中心（RAM 4GB・約2GB）",
}

DEFAULT_MODEL = "qwen2.5:3b"

if "selected_model" not in st.session_state:
    st.session_state.selected_model = DEFAULT_MODEL

SYSTEM_PROMPT = (
    "You are a technical support AI. Answer questions based ONLY on the "
    "provided documents. Follow these rules:\n"
    "1. Write a clear, conversational answer — not just bullet points.\n"
    "2. Naturally embed citations like (p.12) or (Manual p.45) in your text "
    "so the reader knows where each piece of information comes from.\n"
    "3. If the documents do not contain the answer, say: "
    "\"この情報は文書に記載されていません\" / "
    "\"This information is not found in the documents.\"\n"
    "4. Use technical terms accurately.\n"
    "5. Reply in the same language as the user's question "
    "(Japanese or English).\n\n"
    "あなたは製品ドキュメント専門の技術サポートAIです。\n"
    "以下のルールに従ってください：\n"
    "1. 箇条書きだけでなく、自然な会話文で回答する\n"
    "2. 回答文中に (p.12) や (取扱説明書 p.45) のように出典を埋め込む\n"
    "3. 文書に記載がない場合は「この情報は文書に記載されていません」と明示する\n"
    "4. 技術用語は正確に使用する\n"
    "5. ユーザーの質問と同じ言語で回答する"
)


@st.cache_resource
def _create_embedding():
    """Create the HuggingFace embedding model (cached)."""
    # e5-base: half the size of e5-large, practical on CPU-only machines.
    # Still supports 100+ languages including Japanese and English.
    return HuggingFaceEmbedding(
        model_name="intfloat/multilingual-e5-base",
        cache_folder="./models",
    )


def setup_embedding():
    """Initialise embedding model.

    The HuggingFaceEmbedding object is cached, but ``Settings.embed_model``
    is always reassigned so the global state stays consistent.
    """
    Settings.embed_model = _create_embedding()
    return True


@st.cache_resource
def _create_llm(model_name: str):
    """Create an Ollama LLM instance (cached per model name)."""
    return Ollama(
        model=model_name,
        request_timeout=300.0,
        temperature=0.0,
        system_prompt=SYSTEM_PROMPT,
    )


def setup_llm(model_name: str):
    """Initialise (or switch) the active LLM.

    The Ollama object itself is cached, but ``Settings.llm`` is always
    reassigned so that model switching works correctly.
    """
    llm = _create_llm(model_name)
    Settings.llm = llm
    return llm


try:
    setup_embedding()
    setup_llm(st.session_state.selected_model)
except Exception as exc:
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

def _persist_chat_history():
    """Save current chat history to disk."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.chat_history, f, ensure_ascii=False)


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
    # Also persist doc_parts_cache so the Source Viewer works after reload
    cache_file = STORAGE_DIR / "doc_parts_cache.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(st.session_state.doc_parts_cache, f, ensure_ascii=False)

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

    # --- Auto-load persisted index on session start ----------------------
    if STORAGE_DIR.exists() and st.session_state.index is None:
        with st.spinner("保存済みデータを読み込み中..."):
            try:
                storage_context = StorageContext.from_defaults(
                    persist_dir=str(STORAGE_DIR)
                )
                st.session_state.index = load_index_from_storage(storage_context)
                if METADATA_FILE.exists():
                    with open(METADATA_FILE, "r", encoding="utf-8") as f:
                        st.session_state.documents = json.load(f)
                cache_file = STORAGE_DIR / "doc_parts_cache.json"
                if cache_file.exists():
                    with open(cache_file, "r", encoding="utf-8") as f:
                        st.session_state.doc_parts_cache = json.load(f)
                # Flag saved chat history for restore prompt (shown in Chat area)
                if CHAT_HISTORY_FILE.exists():
                    st.session_state.chat_history_offer = True
                st.success(
                    f"前回のデータを復元しました（{len(st.session_state.documents)}件）"
                )
            except Exception as exc:
                st.error(f"保存データの読み込みに失敗しました: {exc}")

    st.divider()

    # --- File uploader --------------------------------------------------
    uploaded_files = st.file_uploader(
        "PDF文書をアップロード",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        help="取扱説明書、セミナー資料、アプリケーションノート等（PDF推奨）",
    )

    def _make_progress(name, placeholder):
        """Factory to capture *name* and *placeholder* eagerly."""
        def _progress(current: int, total: int):
            placeholder.progress(
                current / total,
                text=f"読み取り中: {name} ({current}/{total} ページ)",
            )
        return _progress

    if uploaded_files:
        new_docs_added = False

        for uploaded_file in uploaded_files:
            fname = uploaded_file.name
            if fname in st.session_state.doc_parts_cache:
                st.info(
                    f"「{fname}」は登録済みのため、スキップしました。"
                    "再登録するには先に「すべてクリア」してください。"
                )
                continue

            uploaded_file.seek(0)

            # Progress bar for PDF extraction (OCR can be slow)
            progress_placeholder = st.empty()
            status_placeholder = st.empty()

            _progress = _make_progress(fname, progress_placeholder)

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

            if doc_parts is not None and len(doc_parts) == 0:
                hint = ""
                if not use_ocr and Path(fname).suffix.lower() == ".pdf":
                    hint = " OCRを有効にすると読み取れる場合があります。"
                st.warning(
                    f"「{fname}」からテキストを抽出できませんでした。"
                    f"白紙またはスキャン画像のみの可能性があります。{hint}"
                )

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
            st.session_state.pending_query = None
            st.session_state.chat_history_offer = False
            if STORAGE_DIR.exists():
                shutil.rmtree(STORAGE_DIR)
            st.rerun()

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.source-page-text {
    font-size: 0.85rem;
    line-height: 1.5;
    white-space: pre-wrap;
    word-wrap: break-word;
    background: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 0.4rem;
    padding: 0.8rem;
    max-height: 52vh;
    overflow-y: auto;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Main area — two-column layout (Sources | Chat)
# ---------------------------------------------------------------------------
st.title("Technical Support AI")

if "viewer_doc" not in st.session_state:
    st.session_state.viewer_doc = None
if "viewer_page" not in st.session_state:
    st.session_state.viewer_page = 0

source_col, chat_col = st.columns([2, 3], gap="large")

# ========================== LEFT: Source Viewer ============================
with source_col:
    st.markdown("#### Sources")

    if st.session_state.doc_parts_cache:
        doc_names = list(st.session_state.doc_parts_cache.keys())

        selected_doc = st.selectbox(
            "ドキュメント",
            doc_names,
            index=(
                doc_names.index(st.session_state.viewer_doc)
                if st.session_state.viewer_doc in doc_names
                else 0
            ),
            label_visibility="collapsed",
        )
        st.session_state.viewer_doc = selected_doc

        parts = st.session_state.doc_parts_cache[selected_doc]
        total = len(parts)

        # Clamp viewer_page to valid range (e.g. after switching to a
        # shorter document) so the slider/buttons never receive an
        # out-of-range value.
        max_page = max(total - 1, 0)
        if st.session_state.viewer_page > max_page:
            st.session_state.viewer_page = max_page

        # Find doc metadata for OCR info
        doc_meta = next(
            (d for d in st.session_state.documents if d["name"] == selected_doc),
            {},
        )
        ocr_count = doc_meta.get("ocr_pages", 0)
        info_parts = [f"{total} ページ"]
        if ocr_count:
            info_parts.append(f"OCR {ocr_count}ページ")
        st.caption(" / ".join(info_parts))

        # Page navigation
        nav_c1, nav_c2, nav_c3 = st.columns([1, 3, 1])
        with nav_c1:
            if st.button("◀", disabled=(st.session_state.viewer_page <= 0),
                         use_container_width=True):
                st.session_state.viewer_page -= 1
        with nav_c3:
            if st.button("▶", disabled=(st.session_state.viewer_page >= max_page),
                         use_container_width=True):
                st.session_state.viewer_page += 1
        with nav_c2:
            page_idx = st.slider(
                "ページ",
                0,
                max_page,
                st.session_state.viewer_page,
                label_visibility="collapsed",
            )
            st.session_state.viewer_page = page_idx

        page_idx = st.session_state.viewer_page

        part = parts[page_idx]
        page_num = part["metadata"].get("page", page_idx + 1)
        method = part["metadata"].get("extraction_method", "text")
        method_tag = "  [OCR]" if method == "ocr" else ""
        st.markdown(f"**ページ {page_num} / {total}{method_tag}**")

        # Render page text in a scrollable container (escape to prevent XSS)
        escaped_text = html.escape(part["text"])
        st.markdown(
            f'<div class="source-page-text">{escaped_text}</div>',
            unsafe_allow_html=True,
        )

    else:
        st.info("サイドバーからPDFをアップロードすると\nここに内容が表示されます")
        st.markdown(
            f"""
**使い方**
1. サイドバーからPDFをアップロード
2. ここで内容を確認
3. 右側のチャットで質問

**OCR**: {"利用可能" if OCR_AVAILABLE else "未インストール"}
""",
        )

# ========================== RIGHT: Chat ====================================
with chat_col:
    st.markdown("#### Chat")

    # Scrollable chat area
    chat_container = st.container(height=520)

    with chat_container:
        # Offer to restore saved chat history on startup
        if (
            st.session_state.chat_history_offer
            and not st.session_state.chat_history
            and st.session_state.pending_query is None
        ):
            st.info("前回の会話履歴が保存されています")
            rc1, rc2 = st.columns(2)
            with rc1:
                if st.button("前回の会話を復元", use_container_width=True):
                    try:
                        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                            st.session_state.chat_history = json.load(f)
                    except Exception:
                        st.error("会話履歴の読み込みに失敗しました")
                    st.session_state.chat_history_offer = False
                    st.rerun()
            with rc2:
                if st.button("新しい会話で開始", use_container_width=True):
                    st.session_state.chat_history_offer = False
                    if CHAT_HISTORY_FILE.exists():
                        CHAT_HISTORY_FILE.unlink()
                    st.rerun()
        elif not st.session_state.chat_history and st.session_state.pending_query is None:
            if st.session_state.index is not None:
                st.caption("質問を入力すると、アップロード済み文書から回答します")
            else:
                st.caption("サイドバーからPDFをアップロードしてください")

        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

                if message.get("sources"):
                    with st.expander("参照元", expanded=False):
                        for i, source in enumerate(message["sources"], 1):
                            st.markdown(f"**[{i}] {source['file_name']}**")
                            if source.get("page"):
                                method = source.get("extraction_method", "text")
                                method_label = " [OCR]" if method == "ocr" else ""
                                score_text = (
                                    f"　関連度: {source['score']:.3f}"
                                    if source.get("score") is not None
                                    else ""
                                )
                                st.caption(
                                    f"p.{source['page']}/{source.get('total_pages', '?')}"
                                    f"{method_label}{score_text}"
                                )
                            # "Jump to source" button
                            if source.get("file_name") and source.get("page"):
                                btn_key = f"jump_{message.get('timestamp','')}_{i}"
                                if st.button(
                                    f"p.{source['page']} を表示",
                                    key=btn_key,
                                    type="tertiary",
                                ):
                                    src_name = source["file_name"]
                                    target_page = source["page"]
                                    st.session_state.viewer_doc = src_name
                                    # Find the correct parts index by matching
                                    # the page metadata (empty pages are skipped,
                                    # so parts index != page_number - 1).
                                    cached = st.session_state.doc_parts_cache.get(src_name, [])
                                    page_idx = next(
                                        (
                                            idx
                                            for idx, p in enumerate(cached)
                                            if p["metadata"].get("page") == target_page
                                        ),
                                        max(target_page - 1, 0),  # fallback
                                    )
                                    st.session_state.viewer_page = page_idx
                                    st.rerun()
                            st.divider()

        # --- Phase 2: generate answer for pending query ---------------------
        if st.session_state.pending_query is not None:
            pending = st.session_state.pending_query
            with st.chat_message("assistant"):
                with st.spinner("文書を検索して回答を生成中..."):
                    try:
                        query_engine = st.session_state.index.as_query_engine(
                            similarity_top_k=5,
                            response_mode="compact",
                        )
                        response = query_engine.query(pending["prompt"])
                    except Exception as exc:
                        st.error(
                            f"回答生成エラー: {exc}\n\n"
                            "Ollamaが起動しているか確認してください: `ollama serve`"
                        )
                        st.session_state.pending_query = None
                        st.stop()

                    sources: list[dict] = []
                    for node in response.source_nodes:
                        sources.append(
                            {
                                "file_name": node.metadata.get("file_name", "unknown"),
                                "file_type": node.metadata.get("file_type", ""),
                                "page": node.metadata.get("page"),
                                "total_pages": node.metadata.get("total_pages"),
                                "extraction_method": node.metadata.get(
                                    "extraction_method", "text"
                                ),
                                "score": node.score,
                                "text": node.text,
                            }
                        )

                    answer_text = response.response or "（回答を生成できませんでした）"
                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": answer_text,
                            "sources": sources,
                            "timestamp": pending["timestamp"],
                        }
                    )
                    _persist_chat_history()
                    st.session_state.pending_query = None
                    st.rerun()

    # Quick-question chips (hidden while the restore-chat prompt is active)
    _chat_ready = (
        st.session_state.index is not None
        and not st.session_state.chat_history_offer
    )
    if _chat_ready:
        q1, q2, q3 = st.columns(3)
        with q1:
            if st.button("仕様・スペック", use_container_width=True):
                st.session_state.quick_question = "この製品の主な仕様とスペックを教えてください"
        with q2:
            if st.button("トラブル対処", use_container_width=True):
                st.session_state.quick_question = "よくあるトラブルとその対処法を教えてください"
        with q3:
            if st.button("メンテナンス", use_container_width=True):
                st.session_state.quick_question = "日常的なメンテナンス方法を教えてください"

# ---------------------------------------------------------------------------
# Chat input (full-width, at bottom)
# Phase 1: append user message → rerun immediately so the user sees their
#           message appear.  Phase 2 (inside chat_container above) picks up
#           the pending_query and generates the answer with a visible spinner.
# ---------------------------------------------------------------------------
if _chat_ready:
    prompt = st.chat_input("質問を入力してください（例：ベースライン補正の手順は？）")

    if "quick_question" in st.session_state:
        prompt = st.session_state.quick_question
        del st.session_state.quick_question

    if prompt and st.session_state.pending_query is None:
        timestamp = datetime.now().isoformat()

        st.session_state.chat_history.append(
            {"role": "user", "content": prompt, "timestamp": timestamp}
        )
        # Store the query for Phase 2; rerun so user message is visible first
        st.session_state.pending_query = {
            "prompt": prompt,
            "timestamp": timestamp,
        }
        st.rerun()

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
foot1, foot2, foot3 = st.columns(3)

with foot1:
    _has_chat = bool(st.session_state.chat_history) or st.session_state.chat_history_offer
    if st.button("会話履歴クリア", disabled=not _has_chat):
        st.session_state.chat_history = []
        st.session_state.pending_query = None
        st.session_state.chat_history_offer = False
        if CHAT_HISTORY_FILE.exists():
            CHAT_HISTORY_FILE.unlink()
        st.rerun()

with foot2:
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

with foot3:
    status = "準備完了" if st.session_state.index else "文書待機中"
    docs_n = len(st.session_state.documents)
    st.caption(f"{status} / 登録: {docs_n}件")
