"""
FAQ Manager - FAQ データの管理とベクトル検索を行うクラス
"""
import json
import os
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


class FAQManager:
    """FAQデータの管理とベクトル検索を行うクラス"""

    def __init__(
        self,
        faq_data_path: str = "data/faqs.json",
        vector_db_path: str = "vector_db",
        embedding_model_name: str = "intfloat/multilingual-e5-large"
    ):
        """
        FAQマネージャーの初期化

        Args:
            faq_data_path: FAQデータのJSONファイルパス
            vector_db_path: ChromaDBの保存先パス
            embedding_model_name: 埋め込みモデルの名前
        """
        self.faq_data_path = faq_data_path
        self.vector_db_path = vector_db_path
        self.embedding_model_name = embedding_model_name

        # 埋め込みモデルの初期化
        print(f"埋め込みモデル {embedding_model_name} を読み込み中...")
        self.embedding_model = SentenceTransformer(embedding_model_name)

        # ChromaDBクライアントの初期化
        self.chroma_client = chromadb.PersistentClient(
            path=vector_db_path,
            settings=Settings(anonymized_telemetry=False)
        )

        # コレクションの取得または作成
        self.collection = self.chroma_client.get_or_create_collection(
            name="faq_collection",
            metadata={"hnsw:space": "cosine"}
        )

        self.faqs = []

    def load_faqs(self) -> List[Dict]:
        """
        FAQデータをJSONファイルから読み込む

        Returns:
            FAQデータのリスト
        """
        if not os.path.exists(self.faq_data_path):
            raise FileNotFoundError(f"FAQデータファイルが見つかりません: {self.faq_data_path}")

        with open(self.faq_data_path, 'r', encoding='utf-8') as f:
            self.faqs = json.load(f)

        print(f"{len(self.faqs)}件のFAQデータを読み込みました")
        return self.faqs

    def build_vector_database(self) -> None:
        """
        FAQデータからベクトルデータベースを構築
        """
        if not self.faqs:
            self.load_faqs()

        # 既存データをクリア
        existing_ids = self.collection.get()['ids']
        if existing_ids:
            self.collection.delete(ids=existing_ids)
            print(f"{len(existing_ids)}件の既存データを削除しました")

        # 質問文のリスト
        questions = [faq['question'] for faq in self.faqs]
        ids = [faq['id'] for faq in self.faqs]

        # 埋め込みベクトルを生成
        print("埋め込みベクトルを生成中...")
        embeddings = self.embedding_model.encode(
            questions,
            normalize_embeddings=True,
            show_progress_bar=True
        )

        # メタデータの準備
        metadatas = [
            {
                'question': faq['question'],
                'answer': faq['answer'],
                'related_docs': json.dumps(faq.get('related_docs', []), ensure_ascii=False)
            }
            for faq in self.faqs
        ]

        # ChromaDBに追加
        print("ベクトルデータベースに追加中...")
        self.collection.add(
            embeddings=embeddings.tolist(),
            documents=questions,
            metadatas=metadatas,
            ids=ids
        )

        print(f"✓ {len(self.faqs)}件のFAQをベクトルデータベースに登録しました")

    def search(self, query: str, n_results: int = 3, similarity_threshold: float = 0.5) -> List[Dict]:
        """
        質問文を検索し、類似するFAQを返す

        Args:
            query: 検索クエリ（ユーザーの質問）
            n_results: 返す結果の最大数
            similarity_threshold: 類似度の閾値（0-1）

        Returns:
            検索結果のリスト
        """
        # クエリの埋め込みベクトルを生成
        query_embedding = self.embedding_model.encode(
            [query],
            normalize_embeddings=True
        )

        # ChromaDBで検索
        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=n_results
        )

        # 結果を整形
        search_results = []

        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                # 距離を類似度に変換（cosine distanceの場合: similarity = 1 - distance）
                distance = results['distances'][0][i]
                similarity = 1 - distance

                # 閾値以上の結果のみを返す
                if similarity >= similarity_threshold:
                    metadata = results['metadatas'][0][i]
                    search_results.append({
                        'id': results['ids'][0][i],
                        'question': metadata['question'],
                        'answer': metadata['answer'],
                        'related_docs': json.loads(metadata['related_docs']),
                        'similarity': similarity,
                        'distance': distance
                    })

        return search_results

    def update_database(self) -> None:
        """
        FAQデータを再読み込みし、ベクトルデータベースを更新
        """
        print("FAQデータベースを更新中...")
        self.load_faqs()
        self.build_vector_database()
        print("✓ データベースの更新が完了しました")

    def get_collection_stats(self) -> Dict:
        """
        コレクションの統計情報を取得

        Returns:
            統計情報の辞書
        """
        count = self.collection.count()
        return {
            'total_faqs': count,
            'collection_name': self.collection.name
        }


if __name__ == "__main__":
    # テスト用コード
    import sys

    # プロジェクトルートからの相対パスで動作するように設定
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # FAQマネージャーの初期化
    print("=== FAQマネージャーのテスト ===\n")

    manager = FAQManager()

    # FAQデータの読み込み
    manager.load_faqs()

    # ベクトルデータベースの構築
    manager.build_vector_database()

    # 統計情報の表示
    stats = manager.get_collection_stats()
    print(f"\n統計情報: {stats}")

    # 検索テスト
    print("\n=== 検索テスト ===")
    test_queries = [
        "バンド幅はどれくらいがいいですか？",
        "サンプルの準備方法を教えてください",
        "メンテナンスの頻度は？"
    ]

    for query in test_queries:
        print(f"\n質問: {query}")
        results = manager.search(query, n_results=2)

        if results:
            for i, result in enumerate(results, 1):
                print(f"\n  結果{i} (類似度: {result['similarity']:.3f}):")
                print(f"    質問: {result['question']}")
                print(f"    回答: {result['answer'][:50]}...")
        else:
            print("  該当するFAQが見つかりませんでした")
