"""
LLM Handler - ローカルLLMを使用して回答を生成するクラス
"""
import os
from typing import List, Dict, Optional
from llama_cpp import Llama


class LLMHandler:
    """ローカルLLMを使用して回答を生成するクラス"""

    def __init__(
        self,
        model_path: str = "models/ELYZA-japanese-Llama-2-7b-fast-instruct-q4_K_M.gguf",
        n_ctx: int = 2048,
        n_threads: int = 4,
        temperature: float = 0.7,
        max_tokens: int = 512
    ):
        """
        LLMハンドラーの初期化

        Args:
            model_path: GGUFモデルファイルのパス
            n_ctx: コンテキストウィンドウサイズ
            n_threads: 使用するCPUスレッド数
            temperature: 生成時の温度パラメータ
            max_tokens: 最大生成トークン数
        """
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.llm = None

    def load_model(self) -> None:
        """
        LLMモデルを読み込む
        """
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"モデルファイルが見つかりません: {self.model_path}\n"
                f"モデルをダウンロードしてください。詳細はREADMEを参照してください。"
            )

        print(f"LLMモデル {self.model_path} を読み込み中...")
        self.llm = Llama(
            model_path=self.model_path,
            n_ctx=self.n_ctx,
            n_threads=self.n_threads,
            verbose=False
        )
        print("✓ LLMモデルの読み込みが完了しました")

    def generate_answer(
        self,
        user_question: str,
        search_results: List[Dict],
        enable_llm: bool = True
    ) -> Dict:
        """
        ユーザーの質問と検索結果から回答を生成

        Args:
            user_question: ユーザーの質問
            search_results: FAQ検索結果のリスト
            enable_llm: LLMによる回答生成を有効にするか（Falseの場合は検索結果をそのまま返す）

        Returns:
            生成された回答と関連情報を含む辞書
        """
        if not search_results:
            return self._generate_no_result_response()

        # LLMが無効化されている場合は、最も類似度の高い結果をそのまま返す
        if not enable_llm or self.llm is None:
            return self._generate_simple_response(search_results)

        # LLMを使用して自然な回答を生成
        return self._generate_llm_response(user_question, search_results)

    def _generate_no_result_response(self) -> Dict:
        """
        該当するFAQが見つからない場合のレスポンスを生成

        Returns:
            該当なしレスポンス
        """
        return {
            'answer': (
                "申し訳ございませんが、ご質問に該当するFAQが見つかりませんでした。\n\n"
                "お手数ですが、以下の方法でお問い合わせください：\n"
                "- 質問内容を変えて再度検索する\n"
                "- 部署の担当者に直接お問い合わせください\n"
                "- サポート窓口にメールでお問い合わせください"
            ),
            'related_docs': [],
            'source_faqs': [],
            'has_result': False
        }

    def _generate_simple_response(self, search_results: List[Dict]) -> Dict:
        """
        LLMを使用せずに、検索結果をそのまま返す

        Args:
            search_results: FAQ検索結果

        Returns:
            シンプルなレスポンス
        """
        best_result = search_results[0]

        # 複数の関連FAQがある場合はそれらも含める
        additional_faqs = ""
        if len(search_results) > 1:
            additional_faqs = "\n\n【関連するFAQ】\n"
            for i, result in enumerate(search_results[1:], 2):
                additional_faqs += f"\n{i}. {result['question']}\n"

        answer = best_result['answer'] + additional_faqs

        # 関連ドキュメントを集約
        all_docs = []
        for result in search_results:
            all_docs.extend(result.get('related_docs', []))

        # 重複を除去
        unique_docs = []
        seen_titles = set()
        for doc in all_docs:
            if doc['title'] not in seen_titles:
                unique_docs.append(doc)
                seen_titles.add(doc['title'])

        return {
            'answer': answer,
            'related_docs': unique_docs,
            'source_faqs': [r['question'] for r in search_results],
            'has_result': True,
            'similarity': best_result.get('similarity', 0.0)
        }

    def _generate_llm_response(
        self,
        user_question: str,
        search_results: List[Dict]
    ) -> Dict:
        """
        LLMを使用して自然な回答を生成

        Args:
            user_question: ユーザーの質問
            search_results: FAQ検索結果

        Returns:
            LLMによって生成されたレスポンス
        """
        # プロンプトの構築
        prompt = self._build_prompt(user_question, search_results)

        # LLMで回答を生成
        try:
            output = self.llm(
                prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stop=["</s>", "質問:", "Question:"],
                echo=False
            )

            generated_text = output['choices'][0]['text'].strip()

        except Exception as e:
            print(f"LLM生成エラー: {e}")
            # エラー時は簡易レスポンスにフォールバック
            return self._generate_simple_response(search_results)

        # 関連ドキュメントを集約
        all_docs = []
        for result in search_results:
            all_docs.extend(result.get('related_docs', []))

        # 重複を除去
        unique_docs = []
        seen_titles = set()
        for doc in all_docs:
            if doc['title'] not in seen_titles:
                unique_docs.append(doc)
                seen_titles.add(doc['title'])

        return {
            'answer': generated_text,
            'related_docs': unique_docs,
            'source_faqs': [r['question'] for r in search_results],
            'has_result': True,
            'similarity': search_results[0].get('similarity', 0.0)
        }

    def _build_prompt(self, user_question: str, search_results: List[Dict]) -> str:
        """
        LLMに与えるプロンプトを構築

        Args:
            user_question: ユーザーの質問
            search_results: FAQ検索結果

        Returns:
            プロンプト文字列
        """
        # FAQ情報を整形
        faq_context = ""
        for i, result in enumerate(search_results, 1):
            faq_context += f"\nFAQ{i}:\n"
            faq_context += f"質問: {result['question']}\n"
            faq_context += f"回答: {result['answer']}\n"

        # ELYZA形式のプロンプト
        prompt = f"""<s>[INST] <<SYS>>
あなたは分析業務のサポートを行う親切なアシスタントです。
以下のFAQデータベースの情報を参考にして、ユーザーの質問に対して簡潔で分かりやすい回答を日本語で生成してください。
回答は自然で対話的な文章にしてください。
FAQの内容をそのまま引用するのではなく、ユーザーの質問に合わせて要約・編集してください。
<</SYS>>

【参考となるFAQ情報】
{faq_context}

【ユーザーの質問】
{user_question}

【回答】
[/INST]"""

        return prompt

    def is_model_loaded(self) -> bool:
        """
        モデルがロードされているかを確認

        Returns:
            モデルがロード済みの場合True
        """
        return self.llm is not None


if __name__ == "__main__":
    # テスト用コード
    print("=== LLMハンドラーのテスト ===\n")

    # モックの検索結果
    mock_search_results = [
        {
            'id': 'faq001',
            'question': '一般的に使用するバンド幅は?',
            'answer': '一般的な測定では4cm-1のバンド幅が推奨されます。',
            'related_docs': [
                {'title': 'FTIR測定パラメータガイド', 'path': 'documents/ftir_parameters.pdf'}
            ],
            'similarity': 0.85
        }
    ]

    # LLMなしでのテスト
    handler = LLMHandler()
    print("LLMなしで回答生成テスト:")
    response = handler.generate_answer(
        "バンド幅について教えてください",
        mock_search_results,
        enable_llm=False
    )
    print(f"回答: {response['answer']}\n")
    print(f"関連ドキュメント: {response['related_docs']}\n")

    print("✓ LLMハンドラーの基本機能が正常に動作しました")
