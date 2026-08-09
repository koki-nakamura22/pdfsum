# pdfsum

[![CI](https://github.com/koki-nakamura22/pdfsum/actions/workflows/ci.yml/badge.svg)](https://github.com/koki-nakamura22/pdfsum/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

PDFドキュメントをLLM APIで要約するCLIツール。

## 特徴

- **複数LLM対応** - Google Gemini / Claude / OpenAI を切り替え可能
- **大規模PDF対応** - トークン上限を超えるPDFはチャンク分割して再帰的に要約
- **キャッシュ** - PDFのSHA-256ハッシュで同一ファイルの再処理をスキップ
- **要約の長さ指定** - short / standard / detailed の3段階
- **SQLiteで永続化** - 要約結果の保存・一覧・表示・削除
- 内部実装は [digestkit](https://github.com/koki-nakamura22/inboxkit/tree/main/packages/digestkit) を採用

## 依存パッケージ

| パッケージ | 役割 |
|------------|------|
| [digestkit](https://github.com/koki-nakamura22/inboxkit/tree/main/packages/digestkit) | PDF抽出 / LLM要約 / 永続化パイプライン |
| platformdirs | OS標準の設定・データディレクトリ解決 |
| python-dotenv | `.env` からの環境変数読み込み |

## 必要環境

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（推奨）

## インストール

```bash
uv add pdfsum
# または
pip install pdfsum
```

依存パッケージの [digestkit](https://pypi.org/project/digestkit/) は PyPI から自動で解決されます。

## セットアップ

### APIキーの設定

プロジェクトルートに `.env` ファイルを作成し、使用するプロバイダのAPIキーを設定します。

```bash
# 使用するプロバイダのキーを設定
GEMINI_API_KEY=your-api-key
ANTHROPIC_API_KEY=your-api-key
OPENAI_API_KEY=your-api-key
```

### 設定ファイル（任意）

`~/.config/pdfsum/config.toml` で既定値を変更できます。

```toml
[llm]
provider = "gemini"          # gemini | claude | openai
model = "gemini-3.5-flash-lite"   # デフォルト値（2026-08 時点の選定）

[summary]
default_length = "standard"  # short | standard | detailed

# 全プロンプト共通の追加指示（任意）
# extra_instructions = "目次、謝辞、参考文献一覧は要約対象に含めないでください。"

# 各段階のプロンプトを完全に上書き（任意。未指定ならデフォルト）
# prompt_short = "..."
# prompt_standard = """
# 複数行のカスタムプロンプトも指定可能です。
# TOML の三重引用符を使ってください。
# """
# prompt_detailed = "..."

[database]
path = "~/.local/share/pdfsum/summaries.db"
```

設定ファイルがない場合は上記のデフォルト値が使われます。

## 使い方

### PDFを要約する

```bash
pdfsum summarize document.pdf
pdfsum summarize document.pdf --length detailed
```

### 保存済みの要約を一覧表示

```bash
pdfsum list
pdfsum list --full-id  # 完全なUUIDを表示
```

### 要約の詳細を表示

```bash
pdfsum show <summary-id>  # 8文字のIDプレフィックスでもOK
```

要約時に消費したトークン数 (入力 / 出力) と所要時間も表示されます。
記録が始まる前 (v0.2.1 以前) に保存した要約では省略されます。

### 要約を削除

```bash
pdfsum delete <summary-id>
```

## ライブラリとしての使用

`pdfsum`はPythonコードからも利用できます。

### 基本的な使い方

```python
from pdfsum import create_service

# config.tomlの設定を使用
service = create_service()
summary = service.summarize("document.pdf", "standard")
print(summary.summary_text)
```

### プロバイダとAPIキーを直接指定

```python
from pdfsum import create_service

service = create_service(provider="gemini", api_key="your-api-key")
summary = service.summarize("document.pdf", "detailed")
```

### 環境変数からAPIキーを取得

```python
import os
os.environ["GEMINI_API_KEY"] = "your-api-key"

from pdfsum import create_service

# api_keyを省略すると環境変数から自動取得
service = create_service(provider="gemini")
```

### オプション引数

```python
from pdfsum import create_service

service = create_service(
    provider="claude",
    api_key="your-api-key",
    model="claude-sonnet-4-20250514",       # モデル指定（省略時はプロバイダのデフォルト）
    db_path="~/my-summaries.db",            # キャッシュDBのパス
    extra_instructions="日本語で要約してください",  # 追加指示
)
```

## 対応モデル

以下は **2026-08 時点** のラインナップです（入力上限・出力上限は litellm の
`get_model_info` の値）。「デフォルト」印はそのプロバイダを選んだときの推奨値で、
`config.toml` を用意しない場合に実際に使われるのは Gemini のデフォルト
（`gemini-3.5-flash-lite`）です。

| プロバイダ | モデル | 入力上限 | 出力上限 | デフォルト |
|-----------|--------|---------|---------|-----------|
| Gemini    | gemini-3.5-flash-lite | 1,048,576 | 65,536 | ✅ |
| Gemini    | gemini-3.1-flash-lite | 1,048,576 | 65,536 | |
| Gemini    | gemini-3.6-flash | 1,048,576 | 65,536 | |
| Gemini    | gemini-3.5-flash | 1,048,576 | 65,535 | |
| Claude    | claude-opus-5 | 1,000,000 | 128,000 | |
| Claude    | claude-sonnet-5 | 1,000,000 | 128,000 | ✅ |
| Claude    | claude-haiku-4-5 | 200,000 | 64,000 | |
| OpenAI    | gpt-5.6 | 1,050,000 | 128,000 | |
| OpenAI    | gpt-5.6-terra | 1,050,000 | 128,000 | |
| OpenAI    | gpt-5.6-luna | 1,050,000 | 128,000 | |
| OpenAI    | gpt-5.4-mini | 272,000 | 128,000 | ✅ |
| OpenAI    | gpt-5.4-nano | 272,000 | 128,000 | |

モデル名を変更するときは、litellm がその名前を解決できることを確認してください。
解決できない場合、チャンク分割の閾値がエラーも警告もなく 32,000 tokens に縮退し、
長い PDF の要約品質が静かに落ちます。

```bash
uv run python -c "import litellm; print(litellm.get_model_info('gemini/gemini-3.5-flash-lite')['max_input_tokens'])"
```

## 内部実装

pdfsum の内部処理 (PDF テキスト抽出 / LLM 要約 / SQLite 保存) は [digestkit](https://github.com/koki-nakamura22/inboxkit/tree/main/packages/digestkit) のパイプライン (`Source → Extractor → Summarizer → Sink`) で構成されています。

```
SingleFileSource → digestkit.PDFExtractor → LLMSummarizer/ChunkedLLMSummarizer → PdfsumSink → SQLite (summaries テーブル)
```

判断根拠は `docs/adr/002-adopt-digestkit-internally.md` (MADR v3 形式、ローカルのみ — リポジトリには公開されません) を参照してください。

## 開発

```bash
# テスト
uv run pytest

# カバレッジ付きテスト
uv run pytest --cov=pdfsum

# リント
uv run ruff check src/ tests/

# 型チェック
uv run mypy src/
```
