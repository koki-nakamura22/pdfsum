# pdfsum

PDFドキュメントをLLM APIで要約するCLIツール。

> **2026-05-09 大幅リアーキ**: pdfsum を [digestkit](https://github.com/koki-nakamura22/inboxkit/tree/main/packages/digestkit) ベースで再実装しました
> ([motif-3 ideas docs](https://github.com/koki-nakamura22/) Phase 1 工程「pdfsum を digestkit ベースで再実装」相当)。
> これに伴い旧バージョンが備えていた以下の機能は **digestkit Phase 1 のスコープ外**として一旦落ちています:
>
> - 要約の長さ指定 (`--length short/standard/detailed`)
> - 大規模 PDF のチャンク再帰要約 (digestkit `LLMSummarizer` は単発呼び出し)
> - pdfsum 独自スキーマ + プログラム的公開 API (`pdfsum.create_service` / `SummarizeService`)
>
> これらは digestkit 側の機能ギャップとしてドッグフーディング所見にまとめ、必要なものは
> 順次 digestkit に持ち上げる予定です。

## 特徴 (digestkit ベース)

- **複数 LLM 対応** — Google Gemini / Claude / OpenAI を `config.toml` で切り替え (digestkit 経由 = LiteLLM)
- **ディレクトリ一括 / 単一ファイル両対応** — `summarize <path>` でファイル指定もディレクトリ指定もOK
- **SQLite で永続化** — digestkit `SQLiteSink` の `digests` テーブルに要約を保存・一覧・表示・削除
- **PDF 内容ハッシュによる重複処理スキップ** — digestkit `SeenStore` + `content_sha256_key` で
  同一内容の別パスファイルや、同一パスの内容差し替えにも追随する dedup を有効化

## 必要環境

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（推奨）

## インストール

```bash
git clone git@github.com:koki-nakamura22/pdfsum.git
cd pdfsum
uv sync
```

`digestkit` は inboxkit の `main` ブランチを git URL で取得します
(`pyproject.toml` の `[tool.uv.sources]` 参照)。

## セットアップ

### APIキーの設定

プロジェクトルートに `.env` ファイルを作成し、使用するプロバイダのAPIキーを設定します。

```bash
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
# プロンプトへ追記する追加指示 (任意)
# extra_instructions = "目次、謝辞、参考文献一覧は要約対象に含めないでください。"

[database]
path = "~/.local/share/pdfsum/summaries.db"
```

> 注: 旧バージョンの `summary.default_length` / `summary.prompt_short` 等は本実装では
> 参照されません (digestkit `LLMSummarizer` の prompt template に統合)。

## 使い方

### PDF を要約する

```bash
# 単一 PDF
pdfsum summarize document.pdf

# ディレクトリ配下を一括
pdfsum summarize ./papers
pdfsum summarize ./papers --glob "*.pdf" --limit 10
pdfsum summarize ./papers --dry-run    # シンク書き込みをスキップ
pdfsum summarize ./papers --db-path ./digests.db
```

### 保存済みの要約を一覧表示

```bash
pdfsum list
pdfsum list --full-id   # item_id (絶対パス) を完全表示
```

### 要約の詳細を表示

```bash
# item_id (絶対パス) のパス末尾またはファイル名の部分一致で指定
pdfsum show document
pdfsum show /abs/path/to/document.pdf
```

### 要約を削除

```bash
pdfsum delete document
```

## 対応モデル

`config.toml` の `[llm].model` に文字列で指定。digestkit (LiteLLM) が対応するモデル ID
であれば任意に指定可能です。代表例:

| プロバイダ | モデル例 |
|-----------|----------|
| Gemini    | `gemini-2.5-flash` / `gemini-2.5-pro` |
| Claude    | `claude-haiku-4-5` / `claude-sonnet-4-6` / `claude-opus-4-7` |
| OpenAI    | `gpt-4.1` / `gpt-4.1-mini` / `gpt-5.4` |

## 開発

```bash
uv run pytest
uv run ruff check src/ tests/
uv run mypy src/
```
