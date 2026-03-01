# pdfsum

PDFドキュメントをLLM APIで要約するCLIツール。

## 特徴

- **複数LLM対応** - Google Gemini / Claude / OpenAI を切り替え可能
- **大規模PDF対応** - トークン上限を超えるPDFはチャンク分割して再帰的に要約
- **キャッシュ** - PDFのSHA-256ハッシュで同一ファイルの再処理をスキップ
- **要約の長さ指定** - short / standard / detailed の3段階
- **SQLiteで永続化** - 要約結果の保存・一覧・表示・削除

## 必要環境

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（推奨）

## インストール

```bash
git clone git@github.com:koki-nakamura22/pdfsum.git
cd pdfsum
uv sync
```

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

## 対応エンジン

| プロバイダ | デフォルトモデル | コンテキスト上限 |
|-----------|-----------------|----------------|
| Gemini    | gemini-2.5-flash | 1,000,000 tokens |
| Claude    | claude-3.5-sonnet | 200,000 tokens |
| OpenAI    | gpt-4o-mini | 128,000 tokens |

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
