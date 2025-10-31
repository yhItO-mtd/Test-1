"""
ローカルFAQシステム - Streamlitアプリケーション
"""
import streamlit as st
import os
import sys
from pathlib import Path
import time

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from faq_manager import FAQManager
from llm_handler import LLMHandler


# ページ設定
st.set_page_config(
    page_title="ローカルFAQシステム",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .stAlert {
        margin-top: 1rem;
    }
    .doc-link {
        display: inline-block;
        margin: 0.5rem 0;
        padding: 0.5rem 1rem;
        background-color: #f0f2f6;
        border-radius: 0.5rem;
        text-decoration: none;
        color: #0066cc;
    }
    .doc-link:hover {
        background-color: #e0e2e6;
    }
    .similarity-badge {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        background-color: #28a745;
        color: white;
        border-radius: 0.3rem;
        font-size: 0.8rem;
        margin-left: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_faq_manager():
    """FAQマネージャーの初期化（キャッシュ）"""
    try:
        manager = FAQManager(
            faq_data_path=str(project_root / "data" / "faqs.json"),
            vector_db_path=str(project_root / "vector_db")
        )
        return manager
    except Exception as e:
        st.error(f"FAQマネージャーの初期化エラー: {e}")
        return None


@st.cache_resource
def initialize_llm_handler():
    """LLMハンドラーの初期化（キャッシュ）"""
    try:
        handler = LLMHandler(
            model_path=str(project_root / "models" / "ELYZA-japanese-Llama-2-7b-fast-instruct-q4_K_M.gguf")
        )
        return handler
    except Exception as e:
        st.error(f"LLMハンドラーの初期化エラー: {e}")
        return None


def load_faq_database(faq_manager):
    """FAQデータベースの読み込みとベクトルDB構築"""
    try:
        with st.spinner("FAQデータを読み込み中..."):
            faq_manager.load_faqs()

        # ベクトルDBが空の場合のみ構築
        stats = faq_manager.get_collection_stats()
        if stats['total_faqs'] == 0:
            with st.spinner("ベクトルデータベースを構築中..."):
                faq_manager.build_vector_database()
            st.success("✓ ベクトルデータベースを構築しました")

        return True
    except Exception as e:
        st.error(f"FAQデータベースの読み込みエラー: {e}")
        return False


def display_chat_message(role, content, related_docs=None, similarity=None):
    """チャットメッセージを表示"""
    with st.chat_message(role):
        st.markdown(content)

        # 類似度バッジの表示
        if similarity is not None and similarity > 0:
            st.markdown(
                f'<span class="similarity-badge">類似度: {similarity:.1%}</span>',
                unsafe_allow_html=True
            )

        # 関連ドキュメントの表示
        if related_docs and len(related_docs) > 0:
            st.markdown("---")
            st.markdown("**📚 関連ドキュメント:**")

            for doc in related_docs:
                doc_path = project_root / "data" / doc['path']
                if os.path.exists(doc_path):
                    # ファイルが存在する場合はリンク表示
                    st.markdown(f"📄 [{doc['title']}]({doc_path})")
                else:
                    # ファイルが存在しない場合はテキストのみ表示
                    st.markdown(f"📄 {doc['title']} (ファイル未配置)")


def process_user_question(user_question, faq_manager, llm_handler, use_llm):
    """ユーザーの質問を処理して回答を生成"""

    # ステップ1: FAQ検索
    with st.status("検索中です...", expanded=True) as status:
        st.write("💭 質問を分析しています...")
        time.sleep(0.5)

        st.write("🔍 類似するFAQを検索しています...")
        search_results = faq_manager.search(
            user_question,
            n_results=3,
            similarity_threshold=0.3
        )

        if search_results:
            st.write(f"✓ {len(search_results)}件の関連FAQが見つかりました")
        else:
            st.write("該当するFAQが見つかりませんでした")

        status.update(label="検索完了", state="complete", expanded=False)

    # ステップ2: 回答生成
    if use_llm and llm_handler and search_results:
        with st.status("回答をまとめています...", expanded=True) as status:
            st.write("✍️ LLMが回答を生成しています...")

            # LLMモデルのロード（未ロードの場合）
            if not llm_handler.is_model_loaded():
                try:
                    st.write("📥 LLMモデルを読み込んでいます（初回のみ時間がかかります）...")
                    llm_handler.load_model()
                    st.write("✓ LLMモデルの読み込みが完了しました")
                except Exception as e:
                    st.warning(f"LLMモデルの読み込みに失敗しました: {e}")
                    st.write("💡 LLMなしで回答を表示します")
                    use_llm = False

            if use_llm:
                response = llm_handler.generate_answer(
                    user_question,
                    search_results,
                    enable_llm=True
                )
            else:
                response = llm_handler.generate_answer(
                    user_question,
                    search_results,
                    enable_llm=False
                )

            status.update(label="回答生成完了", state="complete", expanded=False)
    else:
        # LLMを使用しない場合
        if llm_handler:
            response = llm_handler.generate_answer(
                user_question,
                search_results,
                enable_llm=False
            )
        else:
            # LLMハンドラーが初期化できていない場合
            if not search_results:
                response = {
                    'answer': "申し訳ございませんが、ご質問に該当するFAQが見つかりませんでした。",
                    'related_docs': [],
                    'has_result': False
                }
            else:
                best_result = search_results[0]
                response = {
                    'answer': best_result['answer'],
                    'related_docs': best_result.get('related_docs', []),
                    'has_result': True,
                    'similarity': best_result.get('similarity', 0.0)
                }

    return response


def main():
    """メイン関数"""

    # タイトル
    st.title("💬 ローカルFAQシステム")
    st.markdown("分析業務に関する質問にお答えします")

    # サイドバー
    with st.sidebar:
        st.header("⚙️ 設定")

        # LLM使用設定
        use_llm = st.checkbox(
            "LLMで回答を生成",
            value=False,
            help="LLMを使用して自然な回答を生成します（処理時間が長くなります）"
        )

        if use_llm:
            st.info("💡 初回のLLM使用時はモデルの読み込みに時間がかかります")

        st.markdown("---")

        # FAQマネージャーの初期化
        faq_manager = initialize_faq_manager()

        if faq_manager:
            # データベース情報
            st.header("📊 データベース情報")

            # 初回起動時または統計情報取得
            if 'db_initialized' not in st.session_state:
                db_loaded = load_faq_database(faq_manager)
                st.session_state['db_initialized'] = db_loaded

            stats = faq_manager.get_collection_stats()
            st.metric("登録FAQ数", f"{stats['total_faqs']}件")

            # データベース更新ボタン
            if st.button("🔄 FAQデータを更新", use_container_width=True):
                with st.spinner("データベースを更新中..."):
                    try:
                        faq_manager.update_database()
                        st.success("✓ データベースを更新しました")
                        st.rerun()
                    except Exception as e:
                        st.error(f"更新エラー: {e}")

        st.markdown("---")
        st.header("ℹ️ 使い方")
        st.markdown("""
        1. 下部の入力欄に質問を入力
        2. Enterキーで送信
        3. 回答と関連ドキュメントが表示されます

        💡 該当するFAQがない場合は、類似する質問が提示されます
        """)

    # LLMハンドラーの初期化
    llm_handler = initialize_llm_handler()

    # チャット履歴の初期化
    if 'messages' not in st.session_state:
        st.session_state.messages = []
        # 初期メッセージ
        st.session_state.messages.append({
            'role': 'assistant',
            'content': 'こんにちは！分析業務に関する質問をお気軽にお尋ねください。'
        })

    # チャット履歴の表示
    for message in st.session_state.messages:
        display_chat_message(
            message['role'],
            message['content'],
            message.get('related_docs'),
            message.get('similarity')
        )

    # ユーザー入力
    if user_question := st.chat_input("質問を入力してください..."):
        # ユーザーメッセージを表示
        st.session_state.messages.append({
            'role': 'user',
            'content': user_question
        })
        display_chat_message('user', user_question)

        # FAQマネージャーが正しく初期化されているか確認
        if not faq_manager:
            error_msg = "FAQマネージャーが初期化されていません。サイドバーの設定を確認してください。"
            st.session_state.messages.append({
                'role': 'assistant',
                'content': error_msg
            })
            display_chat_message('assistant', error_msg)
            st.stop()

        # 回答を生成
        response = process_user_question(
            user_question,
            faq_manager,
            llm_handler,
            use_llm
        )

        # アシスタントの回答を表示
        st.session_state.messages.append({
            'role': 'assistant',
            'content': response['answer'],
            'related_docs': response.get('related_docs', []),
            'similarity': response.get('similarity')
        })
        display_chat_message(
            'assistant',
            response['answer'],
            response.get('related_docs', []),
            response.get('similarity')
        )


if __name__ == "__main__":
    main()
