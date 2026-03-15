#!/usr/bin/env python3
"""NB_Tech_Sys プロジェクトドキュメント DOCX 生成スクリプト"""

from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
import os

def set_cell_shading(cell, color_hex):
    """テーブルセルの背景色を設定"""
    shading = cell._element.get_or_add_tcPr()
    shading_elem = shading.makeelement(qn('w:shd'), {
        qn('w:fill'): color_hex,
        qn('w:val'): 'clear'
    })
    shading.append(shading_elem)

def add_styled_table(doc, headers, rows, col_widths=None):
    """スタイル付きテーブルを追加"""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'

    # ヘッダー行
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = header
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_shading(cell, '1a73e8')

    # データ行
    for r, row_data in enumerate(rows):
        for c, cell_text in enumerate(row_data):
            cell = table.rows[r + 1].cells[c]
            cell.text = str(cell_text)
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(9)
            if r % 2 == 1:
                set_cell_shading(cell, 'f0f4ff')

    if col_widths:
        for i, width in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Cm(width)

    return table


def main():
    doc = Document()

    # ページ設定
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    # デフォルトフォント設定
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Yu Gothic'
    font.size = Pt(10)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), 'Yu Gothic')

    # ==============================
    # 表紙
    # ==============================
    for _ in range(6):
        doc.add_paragraph()

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run('NB_Tech_Sys')
    run.font.size = Pt(36)
    run.bold = True
    run.font.color.rgb = RGBColor(0x1a, 0x73, 0xe8)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run('技術サポート RAG システム')
    run.font.size = Pt(20)
    run.font.color.rgb = RGBColor(0x5f, 0x63, 0x68)

    doc.add_paragraph()

    desc = doc.add_paragraph()
    desc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = desc.add_run('プロジェクト技術ドキュメント')
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0x5f, 0x63, 0x68)

    for _ in range(6):
        doc.add_paragraph()

    ver = doc.add_paragraph()
    ver.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = ver.add_run('Version 1.0  |  2026年2月')
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    doc.add_page_break()

    # ==============================
    # 目次
    # ==============================
    doc.add_heading('目次', level=1)
    toc_items = [
        '1. システム概要',
        '2. ディレクトリ構成',
        '3. 使用ライブラリ・ツール一覧',
        '4. 外部ツール・AI モデル',
        '5. システムアーキテクチャ',
        '6. 処理フロー',
        '7. 画面構成（3パネル UI）',
        '8. 主要機能一覧',
        '9. データ永続化',
        '10. UI テーマ・デザイン',
        '11. 動作要件',
        '12. セットアップ手順',
        '13. 使い方',
    ]
    for item in toc_items:
        p = doc.add_paragraph(item)
        p.paragraph_format.space_after = Pt(4)

    doc.add_page_break()

    # ==============================
    # 1. システム概要
    # ==============================
    doc.add_heading('1. システム概要', level=1)

    doc.add_paragraph(
        'NB_Tech_Sys は、技術ドキュメント（PDF / DOCX / PPTX / TXT / MD）をアップロードし、'
        'ローカル LLM に対して質問応答ができる Retrieval-Augmented Generation (RAG) システムです。'
    )
    doc.add_paragraph(
        'Google NotebookLM にインスパイアされた3パネル構成の Web UI を備え、'
        'ドキュメントの意味検索・ソース帰属表示・クイックアクション（要約・FAQ生成等）を提供します。'
    )

    doc.add_heading('特徴', level=2)
    features_intro = [
        'クラウド API 不要 — Ollama を使い全てローカルで動作',
        '多言語対応 — 日本語を含む多言語埋め込みモデルを使用',
        'マルチフォーマット — PDF / Word / PowerPoint / テキスト / Markdown に対応',
        'ストリーミング応答 — トークン単位でリアルタイム表示',
        'ソース帰属 — 回答の根拠となったドキュメント・ページ番号を表示',
        'ワンクリック操作 — 要約・FAQ・仕様一覧・トラブルシューティングをボタン一つで生成',
        '会話の永続化 — チャット履歴を自動保存し再起動後も復元',
        'Ollama 自動セットアップ — LLM モデル未インストール時に自動ダウンロード',
    ]
    for f in features_intro:
        doc.add_paragraph(f, style='List Bullet')

    # ==============================
    # 2. ディレクトリ構成
    # ==============================
    doc.add_heading('2. ディレクトリ構成', level=1)

    dir_rows = [
        ['technical_support_rag.py', 'メインアプリケーション（約1000行）'],
        ['requirements.txt', 'Python 依存ライブラリ一覧'],
        ['install.bat', '初期セットアップ用バッチ（Windows）'],
        ['run.bat', 'アプリ起動用バッチ（Windows）'],
        ['.gitignore', 'Git 除外設定'],
    ]
    add_styled_table(doc, ['ファイル名', '説明'], dir_rows, [5, 11])

    doc.add_paragraph()
    doc.add_paragraph('実行時に自動生成されるディレクトリ:')

    auto_dir_rows = [
        ['storage/', 'ベクトルインデックス・チャット履歴・メタデータ'],
        ['models/', 'HuggingFace 埋め込みモデルのキャッシュ（約1GB）'],
    ]
    add_styled_table(doc, ['ディレクトリ', '内容'], auto_dir_rows, [5, 11])

    # ==============================
    # 3. 使用ライブラリ
    # ==============================
    doc.add_heading('3. 使用ライブラリ・ツール一覧', level=1)

    doc.add_heading('Python パッケージ（requirements.txt）', level=2)

    lib_rows = [
        ['RAG フレームワーク', 'llama-index-core', '>=0.10.0', 'ベクトルインデックス構築・セマンティック検索'],
        ['LLM 連携', 'llama-index-llms-ollama', '>=0.1.0', 'Ollama 経由でローカル LLM を呼び出し'],
        ['埋め込みモデル連携', 'llama-index-embeddings-huggingface', '>=0.1.0', 'HuggingFace 埋め込みモデルとの統合'],
        ['Web UI', 'streamlit', '>=1.36.0', 'ブラウザベースの対話型 UI フレームワーク'],
        ['テキスト埋め込み', 'sentence-transformers', '>=2.2.0', '文章をベクトルに変換するライブラリ'],
        ['深層学習基盤', 'torch', '>=2.0.0', 'sentence-transformers の依存ライブラリ'],
        ['PDF 処理', 'PyPDF2', '>=3.0.0', 'PDF ファイルからテキストをページ単位で抽出'],
        ['Word 処理', 'python-docx', '>=1.0.0', 'DOCX ファイルから段落テキストを抽出'],
        ['PowerPoint 処理', 'python-pptx', '>=0.6.23', 'PPTX ファイルからスライドテキストを抽出'],
        ['システム情報', 'psutil', '>=5.9.0', 'CPU 物理コア数を取得しスレッド数を最適化'],
    ]
    add_styled_table(doc, ['カテゴリ', 'ライブラリ', 'バージョン', '用途'], lib_rows, [3.5, 4.5, 2, 6])

    # ==============================
    # 4. 外部ツール
    # ==============================
    doc.add_heading('4. 外部ツール・AI モデル', level=1)

    doc.add_heading('外部ツール', level=2)
    ext_rows = [
        ['Ollama', 'ローカル LLM ランタイム', 'https://ollama.ai', 'LLM をローカルで実行するためのエンジン。クラウド API 不要。'],
    ]
    add_styled_table(doc, ['ツール', '種別', 'URL', '説明'], ext_rows, [3, 3, 4, 6])

    doc.add_paragraph()
    doc.add_heading('AI モデル', level=2)
    model_rows = [
        ['qwen3.5:4b', 'LLM（大規模言語モデル）', '約2.5GB', '質問に対する回答を生成。Ollama 経由でダウンロード・実行。'],
        ['BAAI/bge-m3', '埋め込みモデル', '約2GB', 'テキストをベクトルに変換。CJK（中日英）特化、8192トークン対応。HuggingFace からダウンロード。'],
    ]
    add_styled_table(doc, ['モデル名', '種別', 'サイズ', '説明'], model_rows, [4.5, 3.5, 2, 6])

    # ==============================
    # 5. システムアーキテクチャ
    # ==============================
    doc.add_heading('5. システムアーキテクチャ', level=1)

    doc.add_paragraph(
        '本システムは以下の3層で構成されています。'
    )

    doc.add_heading('プレゼンテーション層（Streamlit UI）', level=2)
    doc.add_paragraph(
        'Streamlit フレームワークを使用した Web ベースの UI。'
        'NotebookLM 風の3パネルレイアウト（ソース管理・チャット・スタジオ）を提供します。'
        'カスタム CSS により温かみのあるベージュ系の配色テーマを適用しています。'
    )

    doc.add_heading('RAG エンジン層（LlamaIndex）', level=2)
    doc.add_paragraph(
        'LlamaIndex の VectorStoreIndex を中核とする検索エンジン。'
        'アップロードされたドキュメントをチャンク化し、埋め込みモデルでベクトル化してインデックスに格納します。'
        'ユーザーの質問に対して類似度上位3件のチャンクを検索し、LLM へのコンテキストとして提供します。'
    )
    arch_details = [
        'インデックス方式: VectorStoreIndex（ベクトル類似度検索）',
        '検索パラメータ: similarity_top_k=3',
        '応答モード: compact（簡潔な要約形式）',
        'ストリーミング応答: トークン単位でリアルタイム表示',
        'メタデータフィルタ: ファイル名ベースで選択ソースのみに絞り込み可能',
    ]
    for d in arch_details:
        doc.add_paragraph(d, style='List Bullet')

    doc.add_heading('AI モデル層（Ollama + HuggingFace）', level=2)
    doc.add_paragraph(
        'Ollama が qwen3.5:4b モデルを実行し、検索結果をコンテキストとして回答を生成します。'
        '埋め込みには HuggingFace の BGE-M3 を使用し、CJK（中国語・日本語・英語）に特化した高精度な検索を実現しています。'
    )
    ai_details = [
        'LLM 温度パラメータ: 0.1（ほぼ確定的な応答）',
        'コンテキストウィンドウ: num_ctx=8192',
        'CPU スレッド数: 物理コア数を自動検出して設定',
        'システムプロンプト: 提供されたドキュメントのみを使用して回答するよう指示（日本語）',
        'リクエストタイムアウト: 300秒',
    ]
    for d in ai_details:
        doc.add_paragraph(d, style='List Bullet')

    # ==============================
    # 6. 処理フロー
    # ==============================
    doc.add_heading('6. 処理フロー', level=1)

    doc.add_heading('6.1 セットアップフロー（install.bat）', level=2)
    setup_steps = [
        ['1', 'Python バージョン確認', 'Python 3.10 以上がインストール済みか検証'],
        ['2', '仮想環境作成', '%USERPROFILE%\\.nb_tech_venv に Python 仮想環境を構築'],
        ['3', 'pip アップグレード', 'pip 自体を最新版に更新して依存解決エラーを防止'],
        ['4', 'パッケージインストール', 'requirements.txt から全依存ライブラリをインストール'],
        ['5', '埋め込みモデル DL', 'BGE-M3（約2GB）を事前ダウンロード'],
        ['6', 'Ollama 確認', 'Ollama のインストール状況を確認、案内を表示'],
        ['7', 'LLM モデル DL', 'qwen3.5:4b（約2.5GB）を Ollama 経由でダウンロード'],
    ]
    add_styled_table(doc, ['順序', '処理', '詳細'], setup_steps, [1.5, 4, 10.5])

    doc.add_paragraph()
    doc.add_heading('6.2 ドキュメント処理フロー', level=2)
    doc_steps = [
        ['1', 'ファイルアップロード', 'サイドバーから PDF / DOCX / PPTX / TXT / MD をアップロード'],
        ['2', 'テキスト抽出', 'ファイル形式に応じた専用パーサーでテキストを抽出'],
        ['3', 'メタデータ付与', 'ファイル名・種別・ページ番号/スライド番号を各チャンクに付与'],
        ['4', 'ベクトル化', '埋め込みモデルでテキストをベクトルに変換'],
        ['5', 'インデックス構築', 'VectorStoreIndex を作成（既存の場合は追加）'],
        ['6', '永続化', 'storage/ ディレクトリにインデックスとメタデータを保存'],
    ]
    add_styled_table(doc, ['順序', '処理', '詳細'], doc_steps, [1.5, 4, 10.5])

    doc.add_paragraph()
    doc.add_heading('6.3 質問応答フロー', level=2)
    qa_steps = [
        ['1', '質問入力', 'ユーザーがチャット欄に質問を入力、またはクイックアクションをクリック'],
        ['2', 'メタデータフィルタ', '選択中のソースでフィルタリング条件を構築'],
        ['3', 'セマンティック検索', '類似度上位3件のチャンクをインデックスから検索'],
        ['4', '回答生成（ストリーミング）', 'Ollama（qwen3.5:4b）が検索結果をコンテキストとしてトークン単位で回答を生成'],
        ['5', 'ソース帰属', '回答の根拠となったドキュメント・ページ情報を付与'],
        ['6', '表示・保存', 'チャットパネルに表示、chat_history.json に永続化'],
    ]
    add_styled_table(doc, ['順序', '処理', '詳細'], qa_steps, [1.5, 4, 10.5])

    doc.add_paragraph()
    doc.add_heading('6.4 ドキュメント形式別テキスト抽出', level=2)
    extract_rows = [
        ['PDF', 'PyPDF2', 'ページ単位で抽出。空ページはスキップ。ページ番号をメタデータに記録。'],
        ['DOCX', 'python-docx', '全段落をまとめて1ドキュメントとして抽出。'],
        ['PPTX', 'python-pptx', 'スライド単位で抽出。各スライドのテキストシェイプを結合。スライド番号をメタデータに記録。'],
        ['TXT', '標準ライブラリ', 'UTF-8 でファイル全体を読み込み、1ドキュメントとして処理。'],
        ['MD', '標準ライブラリ', 'UTF-8 でファイル全体を読み込み、プレーンテキストとして処理。'],
    ]
    add_styled_table(doc, ['形式', '使用ライブラリ', '抽出方式'], extract_rows, [2, 3, 11])

    # ==============================
    # 7. 画面構成
    # ==============================
    doc.add_heading('7. 画面構成（3パネル UI）', level=1)

    doc.add_paragraph(
        'Google NotebookLM にインスパイアされた3パネル構成です。'
    )

    doc.add_heading('ソースパネル（左サイドバー）', level=2)
    source_features = [
        'ファイルアップロード領域（PDF / DOCX / PPTX / TXT / MD 対応、ドラッグ＆ドロップ可）',
        'アップロード完了後にアップローダーを自動クリア（同名ファイルの再登録防止）',
        'アップロード済みソースの一覧表示（ファイル種別アイコン付き）',
        'チェックボックスによるソース個別選択/解除',
        '✕ ボタンによるソース個別削除（インデックス内の孤立ノードはフィルタで除外）',
        '選択件数バッジ（例: 「3/5 件選択中」）',
        '「すべてクリア」ボタン（ドキュメント・インデックス・会話を全削除）',
        '「会話をクリア」ボタン（ドキュメントは保持し会話のみ削除）',
    ]
    for f in source_features:
        doc.add_paragraph(f, style='List Bullet')

    doc.add_heading('チャットパネル（中央メイン）', level=2)
    chat_features = [
        '会話履歴の表示（ユーザー/AI のロールアイコン付き）',
        '質問入力欄',
        'ソース参照の展開表示（ドキュメント名・ページ・関連度スコア）',
        'ファイル種別の色分けアイコン（PDF=赤, DOCX=青, PPTX=オレンジ, TXT=グレー）',
    ]
    for f in chat_features:
        doc.add_paragraph(f, style='List Bullet')

    doc.add_heading('スタジオパネル（右サイドバー）', level=2)
    studio_features = [
        'クイックアクションボタン（4種類）:',
    ]
    for f in studio_features:
        doc.add_paragraph(f, style='List Bullet')

    action_rows = [
        ['要約生成', '全ドキュメントの主要内容を簡潔に要約'],
        ['FAQ 作成', 'ドキュメントに基づく想定 Q&A を生成'],
        ['仕様一覧', '仕様・スペック情報を箇条書きで抽出'],
        ['トラブルシューティング', 'よくあるエラーと対処法を一覧生成'],
    ]
    add_styled_table(doc, ['アクション', '説明'], action_rows, [4, 12])

    doc.add_paragraph()
    doc.add_paragraph(
        'クイックアクションの結果はスタジオパネル内ではなく、'
        '中央のチャットパネルに通常の会話と同じ形式で表示されます。'
    )
    doc.add_paragraph()
    doc.add_paragraph('その他のスタジオパネル機能:')
    studio_other = [
        '参照セクション — 最新の回答で使用されたソース上位5件を表示',
        'ステータス表示 — 選択中のソース数を表示',
        'エクスポートボタン — 会話全体を JSON ファイルとしてダウンロード',
    ]
    for f in studio_other:
        doc.add_paragraph(f, style='List Bullet')

    # ==============================
    # 8. 主要機能一覧
    # ==============================
    doc.add_heading('8. 主要機能一覧', level=1)

    func_rows = [
        ['マルチフォーマット対応', 'PDF / DOCX / PPTX / TXT / MD の5形式に対応'],
        ['セマンティック検索', '意味的な類似度に基づくドキュメント横断検索'],
        ['ソース帰属表示', '回答の根拠となったドキュメント・ページ番号を明示'],
        ['ソースフィルタリング', '特定のドキュメントのみに絞った質問が可能'],
        ['チャット永続化', '会話履歴を JSON で自動保存・アプリ再起動時に復元'],
        ['クイックアクション', 'ワンクリックで要約・FAQ・仕様一覧・トラブルシューティングを生成'],
        ['会話エクスポート', 'チャット全体を JSON ファイルとしてダウンロード可能'],
        ['完全ローカル動作', 'クラウド API 不要、全処理をローカルマシンで完結'],
        ['多言語対応', '埋め込みモデルが多言語対応（日本語を含む100以上の言語）'],
        ['NotebookLM 風 UI', '温かみのあるベージュ系配色、3パネル構成のモダンな UI'],
        ['ストリーミング応答', 'トークン単位でリアルタイムに回答を表示'],
        ['Ollama 自動セットアップ', 'LLM モデル未インストール時にプログレス付きで自動ダウンロード'],
        ['CPU 最適化', '物理コア数を自動検出し Ollama のスレッド数を最適化'],
        ['埋め込みモデル変更検知', 'モデル変更時に旧インデックスを自動破棄し再構築を促す'],
        ['エラーハンドリング', 'Ollama 未起動・破損ファイル等に対する適切なエラー表示'],
        ['自動インデックス保存', 'ドキュメント追加・削除時にインデックスを自動永続化'],
    ]
    add_styled_table(doc, ['機能', '説明'], func_rows, [4, 12])

    # ==============================
    # 9. データ永続化
    # ==============================
    doc.add_heading('9. データ永続化', level=1)

    persist_rows = [
        ['storage/', 'LlamaIndex ベクトルインデックスファイル群'],
        ['storage/metadata.json', 'アップロード済みドキュメントの一覧（ファイル名・種別・アップロード日時）'],
        ['storage/chat_history.json', '全チャット履歴（メッセージ本文 + ソース参照情報）'],
        ['models/', 'HuggingFace 埋め込みモデルのローカルキャッシュ'],
    ]
    add_styled_table(doc, ['パス', '内容'], persist_rows, [5, 11])

    # ==============================
    # 10. UI テーマ
    # ==============================
    doc.add_heading('10. UI テーマ・デザイン', level=1)

    doc.add_paragraph('NotebookLM にインスパイアされたカスタム CSS テーマを適用しています。')

    theme_rows = [
        ['背景色', '#f8f6f1', 'ウォームベージュ'],
        ['サイドバー背景', '#f0ece4', 'ライトベージュ'],
        ['カード背景', '#ffffff', 'ホワイト（ボーダー: #e8e4dc）'],
        ['プライマリカラー', '#1a73e8', 'Google ブルー'],
        ['メインテキスト色', '#1f1f1f', 'ダークグレー'],
        ['サブテキスト色', '#5f6368', 'ミディアムグレー'],
        ['カード角丸', '16px', '—'],
        ['ボタン角丸', '20px', '—'],
        ['ソースバッジ', 'ライトブルー', 'ピル型インジケーター'],
    ]
    add_styled_table(doc, ['要素', '値', '備考'], theme_rows, [4, 4, 8])

    # ==============================
    # 11. 動作要件
    # ==============================
    doc.add_heading('11. 動作要件', level=1)

    req_rows = [
        ['OS', 'Windows 10/11（バッチファイル提供）', 'Python コード自体は OS 非依存'],
        ['Python', '3.10 以上', 'python.org からインストール'],
        ['Ollama', '最新版', 'https://ollama.ai からインストール'],
        ['ディスク容量', '約 6GB 以上', '埋め込みモデル 1GB + LLM 5GB + パッケージ類'],
        ['メモリ（RAM）', '8GB 以上推奨', 'モデルロード時に大量のメモリを使用'],
        ['ネットワーク', '初回セットアップ時のみ', 'モデル・パッケージのダウンロードに必要'],
    ]
    add_styled_table(doc, ['項目', '要件', '備考'], req_rows, [3, 5, 8])

    # ==============================
    # 12. セットアップ手順
    # ==============================
    doc.add_heading('12. セットアップ手順', level=1)

    doc.add_heading('前提条件', level=2)
    prereqs = [
        'Python 3.10 以上がインストールされていること',
        'Ollama がインストールされ、起動していること',
        'インターネット接続があること（初回のみ）',
    ]
    for p in prereqs:
        doc.add_paragraph(p, style='List Bullet')

    doc.add_heading('手順', level=2)
    setup_instructions = [
        ('Step 1', 'install.bat をダブルクリックして実行します。'),
        ('Step 2', '自動的に仮想環境の作成、パッケージのインストール、AI モデルのダウンロードが行われます。'),
        ('Step 3', 'Ollama の確認画面が表示されたら、Ollama が起動していることを確認して任意のキーを押します。'),
        ('Step 4', 'LLM モデル（qwen3.5:4b）のダウンロードが完了すると「セットアップ完了!」と表示されます。'),
        ('Step 5', '以後は run.bat をダブルクリックするだけでアプリが起動します。'),
    ]
    for step, desc in setup_instructions:
        p = doc.add_paragraph()
        run = p.add_run(step + ': ')
        run.bold = True
        p.add_run(desc)

    doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run('注意: ')
    run.bold = True
    run.font.color.rgb = RGBColor(0xCC, 0x00, 0x00)
    p.add_run(
        '初回セットアップには埋め込みモデル（約1GB）と LLM モデル（約5GB）の'
        'ダウンロードが含まれるため、回線速度によっては時間がかかります。'
    )

    # ==============================
    # 13. 使い方
    # ==============================
    doc.add_heading('13. 使い方', level=1)

    doc.add_heading('13.1 アプリの起動', level=2)
    doc.add_paragraph('run.bat をダブルクリックすると、ブラウザが自動的に開きアプリが表示されます。')

    doc.add_heading('13.2 ドキュメントのアップロード', level=2)
    upload_steps = [
        '左サイドバーの「ファイルをアップロード」エリアにファイルをドラッグ&ドロップ（または「Browse files」をクリック）',
        '対応形式: PDF / DOCX / PPTX / TXT / MD',
        '複数ファイルの同時アップロードが可能',
        'アップロード完了後、自動的にインデックスが構築されアップローダーがクリアされます',
    ]
    for s in upload_steps:
        doc.add_paragraph(s, style='List Bullet')

    doc.add_heading('13.3 質問する', level=2)
    qa_usage = [
        '中央のチャット欄に質問を入力して Enter キーを押す',
        'AI がアップロードされたドキュメントの内容に基づいてストリーミングで回答を生成',
        '回答の下に参照元ソース（ドキュメント名・ページ番号）が表示される',
    ]
    for s in qa_usage:
        doc.add_paragraph(s, style='List Bullet')

    doc.add_heading('13.4 クイックアクションの使用', level=2)
    doc.add_paragraph(
        '右のスタジオパネルにある4つのボタンをクリックすると、'
        'ワンクリックで以下の操作が実行され、結果はチャットパネルに表示されます:'
    )
    quick_actions_usage = [
        '要約生成 — 全ドキュメントの主要内容を簡潔に要約',
        'FAQ 作成 — よくある質問と回答を生成',
        '仕様一覧 — 技術仕様やスペックを抽出してリスト化',
        'トラブルシューティング — よくあるエラーと対処法を一覧生成',
    ]
    for s in quick_actions_usage:
        doc.add_paragraph(s, style='List Bullet')

    doc.add_heading('13.5 ソースの管理', level=2)
    doc.add_paragraph(
        '左サイドバーで各ソースのチェックボックスをオン/オフすることで、'
        '特定のドキュメントのみを対象に質問できます。'
        '各ソースの右にある✕ボタンで個別に削除することも可能です。'
    )

    doc.add_heading('13.6 会話のエクスポート', level=2)
    doc.add_paragraph(
        '右のスタジオパネル下部にある「会話をエクスポート」ボタンをクリックすると、'
        'チャット全体を JSON ファイルとしてダウンロードできます。'
    )

    # 保存
    output_path = os.path.join(os.path.dirname(__file__), 'NB_Tech_Sys_Document.docx')
    doc.save(output_path)
    print(f'DOCX saved: {output_path}')
    return output_path


if __name__ == '__main__':
    main()
