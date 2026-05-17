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
model = "gemini-2.5-flash"

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

| プロバイダ | モデル | 入力上限 | 出力上限 | デフォルト |
|-----------|--------|---------|---------|-----------|
| Gemini    | gemini-2.5-flash | 1,048,576 | 65,535 | ✅ |
| Gemini    | gemini-2.5-flash-lite | 1,048,576 | 65,535 | |
| Gemini    | gemini-2.5-pro | 1,048,576 | 65,535 | |
| Claude    | claude-opus-4-6 | 1,000,000 | 128,000 | |
| Claude    | claude-sonnet-4-6 | 1,000,000 | 64,000 | ✅ |
| Claude    | claude-haiku-4-5-20251001 | 200,000 | 64,000 | |
| OpenAI    | gpt-5.4 | 1,000,000 | 128,000 | |
| OpenAI    | gpt-5.4-mini | 400,000 | 128,000 | |
| OpenAI    | gpt-5.4-nano | 400,000 | 128,000 | |
| OpenAI    | gpt-4.1 | 1,047,576 | 32,768 | |
| OpenAI    | gpt-4.1-mini | 1,047,576 | 32,768 | ✅ |
| OpenAI    | gpt-4.1-nano | 1,047,576 | 32,768 | |

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
